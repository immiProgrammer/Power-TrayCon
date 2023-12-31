
import sys
import typing
from PyQt5 import QtGui
from PyQt5.QtCore import Qt, QSettings, QTimer, pyqtSignal, QFile, QDate, QTime, QProcess, QSize, QUrl
from PyQt5.QtGui import QIcon, QPixmap, QColor, QFont, QDesktopServices
from PyQt5.QtWidgets import QApplication, QColorDialog, QWidget, QToolButton, QFontDialog, QSpinBox, QVBoxLayout, QDialog, QButtonGroup, QSystemTrayIcon, QLineEdit, QPushButton, QGridLayout, QHBoxLayout, QLabel, QMenu, QAction
from enum import Enum
import json
from pathlib import Path
from csv import writer as csvWriter
from batteryGetter import BatteryStatus
from _rc import resource
import os
from QtHelper.components.SystemTrayIcon import SystemTrayIcon as CSystemTrayIcon




def getFont(fontSize=14, weight=QFont.Normal):
    font = QFont()
    font.setFamilies(['Segoe UI', 'Microsoft YaHei', 'PingFang SC'])
    font.setFamily(Setting.FontFamily.getValidValue(str))
    font.setPixelSize(fontSize)
    font.setWeight(weight)
    return font

def setQSS(*widgets: QWidget, filePath:str):
    f = QFile(filePath)
    f.open(QFile.ReadOnly)
    qss = str(f.readAll(), encoding='utf-8')
    f.close()
    for widget in widgets:
        widget.setStyleSheet(qss)

class JsonManager:
   
    @classmethod
    def readData(cls):
        try:
            with open(str(settingPath), "r") as file:
                return json.load(file)
        except Exception as e:
            cls.writeData()
            return {}
    
    @classmethod
    def writeData(cls):
        dirManager.validateMainPath()
        with open(str(settingPath), "w") as file:
            json.dump(Setting.toDict(), file)

def writeBatteryStatus(per, pluggedIn:bool):
    date = str(QDate.currentDate().toPyDate())
    with open(str(dirManager.validateMainPath()/(date+'-ptc'+'.csv')), 'a+', newline='') as file:
        csvWriter(file).writerow((QTime.currentTime().toString(), f"{'+'if pluggedIn else '-'}{per}"))

class Setting(Enum):
    OnChargingColor = '#24f000'
    NormalColor = '#1ee7fd'
    LowColor = '#ff0f0f'
    CriticalColor = '#df00da'
    
    FontSize = 14
    FontFamily = 'Arial Rounded MT Bold'
    FontWeight = 75

    LowBatteryLevel = 40
    NormalBatteryLevels = list(range(LowBatteryLevel, 100, 10))
    FullBatteryLevel = 100
    CriticalLevel = 25
    
    updateDelay = 2.5
    HisFileUpdateDelay = 1.5
    
    @classmethod
    def toDict(cls):
        return {member.name: member.value for member in cls}
    
    @classmethod
    def fromDict(cls, d:dict):
        for name, value in d.items():
            try:
                cls[name]._value_ = value
            except:pass
    
    @property
    def v(self):
        return self.value
    
    @v.setter
    def v(self, v):
        self.setValue(v, self.updateFile)
    
    def setValue(self, v, after=lambda:None):
        if self._value_ == v:
            return
        self._value_ = v
        after()
    
    @classmethod
    def updateFile(cls):
        JsonManager.writeData()
    
    def getValidValue(self, cls):
        try:
            v = cls(self.v)
        except:
            v = normalSettings[self.name]
            self.v = v
        
        return v

def getToastIcon(p:QIcon|str):
    return QIcon(QIcon(p).pixmap(32, 32))

class State:
    class Ctuple(tuple):

        def title(self):
            return self[0]+' Notify'
        def message(self, per):
            return self[1] + f'\nBattery is {per}%'
        def icon(self):
            return getToastIcon(self[2])
        def color(self):
            return self[3]

    Low = Ctuple(('Low Battery', 'Pluged-In Your Device', ":immiApplication/icon/LowBattery.png", Setting.LowColor))
    Normal = Ctuple(('Normal Battery', '', ":immiApplication/icon/NormalBattery.png", Setting.NormalColor))#* getToastIcon
    Full = Ctuple(('Full Battery', 'Your Device is Full Charged', ":immiApplication/icon/FullCharging.png", Setting.NormalColor))
    Critical = Ctuple(('Critical Battery', 'Pluged-In Your Device', Low[2], Setting.CriticalColor))
    PluggedIn = Ctuple(('Plugged In', 'Charging...', ":immiApplication/icon/ChargingIn.png", Setting.OnChargingColor))
    PluggedOut = Ctuple(('Plugged Out', '', ":immiApplication/icon/ChargingOut.png", Setting.NormalColor))

class BatterChecker:
    def __init__(self, parent):
        self.previousStatus, self.previousPer = BatteryStatus.get_state()

        self.previousState = State.Normal
        self.trayIcon:SystemTrayIcon = parent
        self.lastFileWriteTime = self.lastNotifyTime = QTime.currentTime()


        self.writeBatteryStatus(force=True)

    def check(self, *args, force=False):
        pluggedIn, per = BatteryStatus.get_state()
        statusIsChanged = pluggedIn != self.previousStatus
        perIsChanged = per != self.previousPer
        batteryStageIsChanged = statusIsChanged or perIsChanged
        
        def getState():
            if pluggedIn and per >= Setting.FullBatteryLevel.v:
                return State.Full
            elif not pluggedIn and per <= Setting.LowBatteryLevel.v:
                if per <= Setting.CriticalLevel.v:
                    return State.Critical
                return State.Low
            elif per in Setting.NormalBatteryLevels.v:
                return State.Normal
        
        state = getState()
        ct = QTime.currentTime()
        
        if not force and not batteryStageIsChanged:
            if (state in [State.Critical, State.Full] and (self.previousState != state or self.lastNotifyTime.secsTo(ct) >= 30)):pass
            else:return
            
        color = Setting.OnChargingColor if pluggedIn else (state.color() if state else Setting.NormalColor)
        state = (State.PluggedIn if pluggedIn else State.PluggedOut) if statusIsChanged else state

        if state in [State.Critical, State.Full]:
            self.lastNotifyTime = ct

        self.previousStatus, self.previousPer, self.previousState = pluggedIn, per, state or State.Normal
        if state:
            self.trayIcon.sendMessage.emit(state)

        self.trayIcon.setPixmap(color, per)
        self.writeBatteryStatus(force=statusIsChanged)
    
    def recheck(self):
        self.check(force=True)
    
    def writeBatteryStatus(self, *args, force=False):
        if force or self.lastFileWriteTime.secsTo(ct:=QTime.currentTime())/60 >= Setting.HisFileUpdateDelay.getValidValue(float):# or self.lastFileWriteTime is None
            writeBatteryStatus(self.previousPer, self.previousStatus)
            self.lastFileWriteTime = ct

class SystemTrayIcon(CSystemTrayIcon):
    sendMessage = pyqtSignal(State.Ctuple)
    
    def __init__(self, parent=None):
        super().__init__(pgIcon, parent)
        self.doubleClicked.connect(lambda:w.setVisible(not w.isVisible()))
        self.batteryChecker = BatterChecker(self)

        self.sendMessage.connect(self._sendMessage)
        
        self.timer = QTimer()
        self.timer.setInterval(int(Setting.updateDelay.getValidValue(float)*1000))
        self.timer.start()
        self.timer.timeout.connect(self.batteryChecker.check)

        self.BSWTimer = QTimer()
        self.BSWTimer.setInterval(30000)
        self.BSWTimer.start()
        self.BSWTimer.timeout.connect(self.batteryChecker.writeBatteryStatus)

        self.menu = QMenu(parent=parent)
        self.menu.addAction(QAction(text=windowTitle, parent=self.menu, triggered=lambda:w.show()))
        self.menu.addAction(QAction(text='Setting', parent=self.menu, triggered=lambda:w.show()))
        self.menu.addAction(QAction(text='Github Repo', parent=self.menu, triggered=AboutDialog.open_github))
        self.menu.addAction(QAction(text='exit', parent=self.menu, triggered=sys.exit))
        self.setContextMenu(self.menu)
      
    def setPixmap(self, color:Setting.LowColor, per:int):
        pixmap = QPixmap()
        svg_string = f'''
        <svg viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
        <text fill="{color.v}" x="10" y="16" font-size="{int(Setting.FontSize.getValidValue(int)*1.33333333333)+1}px" text-anchor="middle" font-weight='{getFontWeightL(Setting.FontWeight.getValidValue(int))}' font-family='{Setting.FontFamily.v}'>{per}</text>
        </svg>'''
        pixmap.loadFromData((svg_string.encode('utf-8')))
        if per >= 100:
            pixmap = ":immiApplication/icon/fullBattery.svg"

        self.setIcon(QIcon(pixmap))
        self.setToolTip(f'Battery is {per}%\nStatus: '+ ('AC (charging)' if self.batteryChecker.previousStatus else 'DC (battery)'))
        
    def _sendMessage(self, state: State.Ctuple):
        self.showMessage(state.title(), state.message(self.batteryChecker.previousPer), state.icon())

class HeadingLabel(QLabel):
    lbFont = getFont(13, QFont.Medium)
    
    def __init__(self, text='', parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setFont(self.lbFont)

class SpinBox(QSpinBox):
    leFont = getFont(13, QFont.Medium)
    def __init__(self, parent, rng=(1, 100), default=int(), ) -> None:
        super().__init__(parent)
        self.setRange(*rng)
        self.setValue(default)
        self.setButtonSymbols(QSpinBox.NoButtons)
    
    def setDefaultSettings(self):
        self.setFixedHeight(30)
        self.setFixedWidth(80)
        self.setFont(SpinBox.leFont)

class PushButton(QPushButton):...
class LineEdit(QLineEdit):...

class AboutDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("About Creator")

        self.setFixedSize(250, 170)

        layout = QVBoxLayout()

        creator_label = QLabel("Creator: 'Immi' (Imran Abid)")
        creator_label.setFont(getFont(16, QFont.Medium))
        
        description_label = QLabel("Feel free to reach out to me whenever you encounter a challenge or require my services.")
        description_label.setFont(getFont(12))
        description_label.setWordWrap(True)
        github_button = QPushButton("GitHub Repository")
        email_button = QPushButton("Email Me")
        github_button.clicked.connect(self.open_github)
        email_button.clicked.connect(self.open_email)

        layout.addWidget(creator_label)
        layout.addWidget(description_label)
        layout.addWidget(github_button)
        layout.addWidget(email_button)

        self.setLayout(layout)

    @classmethod
    def open_github(cls):
        github_url = QUrl("https://github.com/immiProgrammer/Power-TrayCon")
        QDesktopServices.openUrl(github_url)

    @classmethod
    def open_email(cls):
        email_address = "mimranabid2@gmail.com"
        email_url = QUrl("mailto:" + email_address)
        QDesktopServices.openUrl(email_url)

class Demo(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(windowTitle)
        self.pgIcon = pgIcon
        
        self.systemTrayIcon = SystemTrayIcon(self)
        self.systemTrayIcon.batteryChecker.recheck()
        self.systemTrayIcon.show()
        self.secondHand = secondHand(self)
        
        self.setWindowIcon(self.pgIcon)
        setQSS(self, filePath=':immiApplication/stylesheet.qss')
        self.mainLayout = QGridLayout(self)
        self.mainLayout.setContentsMargins(20, 20, 20, 20)
        self.mainLayout.setVerticalSpacing(10)
        self.mainLayout.setHorizontalSpacing(10)
        self._initUi()
        
        self.setFixedSize(303, 500)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowMaximizeButtonHint & ~Qt.WindowMinimizeButtonHint)
        
    def _initUi(self):
        icoSize = QSize(20, 20)
        
        titleL = QLabel(self.windowTitle(), self)
        titleL.setFont(getFont(24, QFont.Medium))
        titleLayout = QHBoxLayout()
        icon = QLabel(self)
        icon.setPixmap(self.pgIcon.pixmap(60, 60))
        aboutBtn = QToolButton(self, clicked=self.secondHand.showAboutDialog)
        aboutBtn.setIcon(QIcon(":immiApplication/icon/about.svg"))
        aboutBtn.setFixedSize(30, 30)
        aboutBtn.setIconSize(icoSize)
        aboutBtn.setObjectName('aboutBtn')
        aboutBtn.setCursor(Qt.PointingHandCursor)
        titleLayout.addWidget(icon, 0, Qt.AlignLeft)
        titleLayout.addWidget(titleL, 2, Qt.AlignLeft)
        titleLayout.addWidget(aboutBtn, 2, Qt.AlignRight|Qt.AlignTop)
        titleLayout.setSpacing(0)
        titleLayout.setContentsMargins(*(0,)*4)

        self.mainLayout.addLayout(titleLayout, 0, 0, 1, 3)
        
        self.initControler()
        self.fontSelectBtn = PushButton(self)
        self.fontLabel = HeadingLabel('Set Font', self)
        self.saveBtn = PushButton('Save', clicked=self._save)
        self.saveBtn.setObjectName('saveBtn')

        self.fontSelectBtn.setFixedHeight(30)

        SpinBox.setDefaultSettings(self.saveBtn)
        self.saveBtn.setDefault(True)

        self.updateFontL()
        self.fontSelectBtn.clicked.connect(self.selectFont)
        
        row = self.mainLayout.rowCount()
        self.mainLayout.addWidget(self.fontLabel, row, 0)
        self.mainLayout.addWidget(self.fontSelectBtn, row, 1, 1, 2)
        
        refrestHL = HeadingLabel('Refresh Interval\nin Seconds', self)
        refreshLE = SpinBox(self, (1, 20), Setting.updateDelay.getValidValue(int))
        refreshLE.setDefaultSettings()
        refreshLE.setFixedWidth(70)
        row +=1
        self.mainLayout.addWidget(refrestHL, row, 0)
        self.mainLayout.addWidget(refreshLE, row, 1)

        row+=1
        showHisBtn = QPushButton(' Open History Folder', self, clicked=self.secondHand.openHistoryFolder)
        showHisBtn.setFixedHeight(30)
        showHisBtn.setIcon(QIcon(":immiApplication/icon/History.svg"))
        showHisBtn.setIconSize(QSize(15, 15))
        showHisBtn.setFont(HeadingLabel.lbFont)
        self.mainLayout.addWidget(showHisBtn, row, 0, 1, self.mainLayout.columnCount())
        
        row +=1
        savelb = HeadingLabel('Save required only when change levels', self)
        savelb.setObjectName('alertLB')
        savelb.setWordWrap(True)
        self.mainLayout.addWidget(savelb, row, 0, 1, 2)
        self.mainLayout.addWidget(self.saveBtn, row, 2, Qt.AlignRight|Qt.AlignBottom)
        del row
    
    def selectFont(self):
        font = QFont()
        
        for mem, func in [(Setting.FontFamily, QFont.setFamily), (Setting.FontSize, QFont.setPointSize), (Setting.FontWeight, QFont.setWeight)]:
            try:
                func(font, mem.v)
            except:
                func(font, normalSettings[mem.name])

        font, ok = QFontDialog.getFont(font, self, self.windowTitle())
        if ok:
            Setting.FontFamily.v, Setting.FontSize.v, Setting.FontWeight.v = font.family(), font.pointSize(), font.weight()
            self.updateFontL()
            self.systemTrayIcon.batteryChecker.recheck()

    def updateFontL(self):
        self.fontSelectBtn.setText(f'{Setting.FontFamily.v},\n{getFontWeightL(Setting.FontWeight.v)}, {Setting.FontSize.v}')

    def initControler(self):
        row = self.mainLayout.rowCount()

        for col, lb in enumerate(['Color', 'Levels']):
            lb = HeadingLabel(lb, self)

            self.mainLayout.addWidget(lb, row, col+1)
            
        class Level:
            def __init__(self, l=None) -> None:
                self.level:Setting = l
            
            def isValid(self):return 
            
            def get(self):
                if self.level == None:return
                if self.level == Setting.NormalBatteryLevels:
                    try:
                        l = [int(l) for l in self.level.v]
                    except:
                        l = normalSettings[self.level.name]
                    value = ', '.join([str(l) for l in l])
                else:
                    value = self.level.getValidValue(int)     
                return value

        LBDict = {
            Setting.CriticalColor: ('Critical Battery', Level(Setting.CriticalLevel)),
            Setting.LowColor: ('Low Battery', Level(Setting.LowBatteryLevel)),
            Setting.NormalColor: ('Normal Battery', Level(Setting.NormalBatteryLevels)),
            Setting.FullBatteryLevel: ('Full Battery', Level(Setting.FullBatteryLevel)),
            Setting.OnChargingColor: ('On Charging', Level()),
        }

        self.colorBtnGroup = QButtonGroup(self)
        self.LEGroup = {}
            
        for row, (mem, (lb, level)) in enumerate(LBDict.items(), row+1):

            lb = HeadingLabel(lb, self)
            self.mainLayout.addWidget(lb, row, 0)

            btn = QPushButton(self)
            btn.setFixedSize(70, 30)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.Type = mem
            if mem != Setting.FullBatteryLevel:
                color = QColor(mem.v)
                if not color.isValid():
                    color = QColor(normalSettings[mem.v])
                btn.setCursor(Qt.PointingHandCursor)
                self.colorBtnGroup.addButton(btn)

            else:
                color = QColor(Qt.white)

                btn.setIcon(QIcon(r":immiApplication/icon/fullBattery.svg"))
                btn.setFont(SpinBox.leFont)

            self.setBtnColor(btn, color)
            self.mainLayout.addWidget(btn, row, 1)

            if (l:=level.get()) != None:
                if isinstance(l, int):
                    le = SpinBox(self, default=l)                
                else:
                    le = LineEdit(self)
                    le.setText(l)
                
                le.Type = mem
                SpinBox.setDefaultSettings(le)
                self.mainLayout.addWidget(le, row, 2)
                self.LEGroup[level.level] = le

        self.colorBtnGroup.buttonClicked.connect(self._onColorBtnClicked)
    
    def _onColorBtnClicked(self, btn: QPushButton):
        color = QColorDialog.getColor(QColor(btn.Type.v), self, self.windowTitle())
        self.setBtnColor(btn, color)
        btn._color = color
        btn.Type.v = color.name()
        self.systemTrayIcon.batteryChecker.recheck()
    
    def setBtnColor(self, btn:QPushButton, color:QColor):
        btn.setStyleSheet('''
                    QPushButton{{
                    background-color: {color};
                    border-radius: 5px;
                    outline: none;
                    border: 1px solid rgb(150, 150, 150);
                    }}'''.format(color=color.name()))
    
    def _save(self):
        for levelmem, le in self.LEGroup.items():
            if levelmem == Setting.NormalBatteryLevels:
                
                v = [a for i in le.text().split(',') if isinstance(a:=eval(i.strip()), int)]
                le.setText(', '.join([str(i) for i in v]))
                levelmem.setValue(v)
                continue
            elif levelmem == Setting.CriticalLevel:
                if le.value() >= self.LEGroup[Setting.LowBatteryLevel].value():
                    le.setValue(max(self.LEGroup[Setting.LowBatteryLevel].value()-1, 0))
            v = le.value()
            levelmem.setValue(v)
        self.secondHand.setBatterySaverCmd()
        self.systemTrayIcon.batteryChecker.recheck()
        Setting.updateFile()

    def closeEvent(self, event):
        event.ignore()
        self.hide()

class secondHand:
    def __init__(self, parent) -> None:
        self.p:Demo = parent
    
    def showAboutDialog(self):
        AboutDialog(self.p).exec()
    
    def openHistoryFolder(self):
        QProcess(self.p).start(f'explorer "{str(historyFolder.absolute())}"')
        
    def setBatterySaverCmd(self):
        QProcess(self.p).start(f'powercfg /setdcvalueindex scheme_current sub_energysaver esbattthreshold {Setting.LowBatteryLevel.getValidValue(int)}')

if __name__ == '__main__':

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)
    
    pgIcon = QIcon(":immiApplication/power_traycon.png")
    windowTitle = "Power TrayCon"

    try:
        if BatteryStatus._hasBattery() and BatteryStatus.get_state()[1]>=0:
            dirManager = DirManager()
            dirManager.chDir2ExeDir()

            
            dataFolder = Path('data')
            historyFolder = dataFolder/ 'history'
            settingPath = str(dataFolder/'data.json')

            dirManager.validateMainPath()


            normalSettings = Setting.toDict()
            Setting.fromDict(JsonManager.readData())
            
            getFontWeightL = lambda i=int():'bold' if i==75 else 'normal'

            w = Demo()
            w.hide()
            w.systemTrayIcon.sendMessage.emit(w.systemTrayIcon.batteryChecker.previousState)
            w.secondHand.setBatterySaverCmd()
            

            dirManager.setAutoStartUp(windowTitle)

        else:
            sticon = QSystemTrayIcon()
            sticon.messageClicked.connect(AboutDialog.open_github)
            sticon.setIcon(pgIcon)
            sticon.show()
            sticon.showMessage(f'Battery Error', f'"{windowTitle}"\nThis device does not come equipped with a battery', getToastIcon(pgIcon))
            QTimer.singleShot(5000, sys.exit)

    except Exception as e:
        with open(Path(os.getcwd(), 'PowerTrayCon.log'), '+a') as file:
            file.write(f'{QTime.currentTime()} {sys.executable} {os.getcwd()}\n{e}')
        raise e
    app.exec_()
