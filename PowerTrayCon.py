import sys
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

def setAutoStartUp(appName=''):
    exe_path = sys.executable
    if not exe_path.endswith('python.exe'):
        settings = QSettings("HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run", QSettings.NativeFormat)
        settings.setValue(appName, exe_path)
        return True
    else:
        return False

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
        with open(str(settingPath), "w") as file:
            json.dump(Setting.toDict(), file)

def writeBatteryStatus(per, pluggedIn:bool):
    date = str(QDate.currentDate().toPyDate())
    with open(str(historyFolder/(date+'-ptc'+'.csv')), 'a+', newline='') as file:
        csvWriter(file).writerow((date, QTime.currentTime().toString(), f"{'+'if pluggedIn else '-'}{per}"))
class Setting(Enum):
    OnChargingColor = '#24f000'
    NormalColor = '#1ee7fd'
    LowColor = '#ff0f0f'
    CriticalColor = '#df00da'
    
    FontSize = 14
    FontFamily = 'Arial Rounded MT Bold'
    FontWeight = 75 # 1=bold, 0=normal # QFont.Bold=75, QFont.Normal=50

    LowBatteryLevel = 40
    NormalBatteryLevels = list(range(30, 100, 5))
    FullBatteryLevel = 98
    CriticalLevel = 25
    
    updateDelay = 2.5 # sec
    HisFileUpdateDelay = 1.5 # min #Example 0.5 min== 30sec
    
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

    Low = Ctuple(('Low Battery', 'Pluged-In Your Device', ":immiApplication/icon/LowBattery.png"))
    Normal = Ctuple(('Normal Battery', '', ":immiApplication/icon/NormalBattery.png"))#* getToastIcon
    Full = Ctuple(('Full Battery', 'Your Device is Full Charged', ":immiApplication/icon/FullCharging.png"))
    Critical = Ctuple(('Critical Battery', 'Pluged-In Your Device', Low[2]))
    PluggedIn = Ctuple(('Plugged In', 'Charging...', ":immiApplication/icon/ChargingIn.png"))
    PluggedOut = Ctuple(('Plugged Out', '', ":immiApplication/icon/ChargingOut.png"))
# counter = 1
class BatterChecker:
    def __init__(self, parent):
        self.previousStatus, self.previousPer = BatteryStatus.get_state()
        # self.previousStatus, self.previousPer = None, None
        self.previousState = State.Normal
        self.trayIcon:SystemTrayIcon = parent
        self.lastFileWriteTime = QTime.currentTime()
        self.firstTime = True
        writeBatteryStatus(self.previousPer, self.previousStatus)

    def check(self):
        # global counter
        # print(counter)
        # counter+=1
        pluggedIn, per = BatteryStatus.get_state()
        
        statusIsChanged = pluggedIn != self.previousStatus
        if not statusIsChanged and per == self.previousPer and not self.firstTime:#
            return
        state = None

        if pluggedIn: # color
            color = Setting.OnChargingColor
        else :
            color = Setting.NormalColor
        
        if statusIsChanged and not self.firstTime:# and not self.firstTime
            if pluggedIn:
                state = State.PluggedIn
            else:
                state = State.PluggedOut

        if pluggedIn and per >= Setting.FullBatteryLevel.v:# Full
            state = State.Full
        elif not pluggedIn and per <= Setting.LowBatteryLevel.v:# Low or Critical
            state = State.Low
            color = Setting.LowColor
            if per <= Setting.CriticalLevel.v: # Critical
                state = State.Critical
                color = Setting.CriticalColor
        
        elif not state and per in Setting.NormalBatteryLevels.v: # Normal
            state = State.Normal
            
        self.firstTime = False
        self.previousStatus, self.previousPer, self.previousState = pluggedIn, per, state or State.Normal
        if state:
            self.trayIcon.sendMessage.emit(state)
        self.trayIcon.setPixmap(color, per)
        if self.lastFileWriteTime.secsTo(ct:=QTime.currentTime())/60 >= Setting.HisFileUpdateDelay.getValidValue(float) or statusIsChanged:# or self.lastFileWriteTime is None
            writeBatteryStatus(per, pluggedIn)
            self.lastFileWriteTime = ct

    def recheck(self): # update to new settings
        self.firstTime = True
        self.check()

class SystemTrayIcon(QSystemTrayIcon):
    sendMessage = pyqtSignal(State.Ctuple)
    
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.batteryChecker = BatterChecker(self)
        # self.setPixmap()
        self.sendMessage.connect(self._sendMessage)
        self.timer = QTimer()
        self.timer.setInterval(int(Setting.updateDelay.getValidValue(float)*1000))
        self.timer.start()
        self.timer.timeout.connect(self.batteryChecker.check)

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
    lbFont = getFont(13, QFont.DemiBold)
    
    def __init__(self, text='', parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setFont(self.lbFont)

class SpinBox(QSpinBox):
    leFont = getFont(13, QFont.DemiBold)
    def __init__(self, parent, rng=(1, 100), default=int(), ) -> None:
        super().__init__(parent)
        self.setRange(*rng)
        self.setValue(default)
        self.setButtonSymbols(QSpinBox.NoButtons)
    
    def setDefaultSettings(self):
        self.setFixedHeight(30)
        self.setFixedWidth(80)
        self.setFont(SpinBox.leFont)

class PushButton(QPushButton):
    ...

class LineEdit(QLineEdit):
    ...

class AboutDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("About Creator")
        # self.setGeometry(100, 100, 400, 200)
        self.setFixedSize(250, 170)

        layout = QVBoxLayout()

        creator_label = QLabel("Creator: 'Immi' (Imran Abid)")
        creator_label.setFont(getFont(16, QFont.DemiBold))
        
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
        github_url = QUrl("https://github.com/immiProgrammer/Power-TrayCon") #!  # Replace with your GitHub repository URL
        QDesktopServices.openUrl(github_url)

    @classmethod
    def open_email(cls):
        email_address = "mimranabid2@gmail.com"  # Replace with your email address
        email_url = QUrl("mailto:" + email_address)
        QDesktopServices.openUrl(email_url)

class Demo(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(windowTitle)
        self.pgIcon = pgIcon
        
        self.systemTrayIcon = SystemTrayIcon(self)
        self.systemTrayIcon.batteryChecker.check()
        self.systemTrayIcon.show()
        
        self.setWindowIcon(self.pgIcon)
        setQSS(self, filePath=':immiApplication/stylesheet.qss')
        # self.setStyleSheet()
        self.mainLayout = QGridLayout(self)
        self.mainLayout.setContentsMargins(20, 20, 20, 20)
        self.mainLayout.setVerticalSpacing(10)
        self.mainLayout.setHorizontalSpacing(10)
        self.secondHand = secondHand(self)
        self._initUi()
        
    def _initUi(self):
        icoSize = QSize(20, 20)
        
        titleL = QLabel(self.windowTitle(), self)
        titleL.setFont(getFont(24, QFont.DemiBold))
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
        # titleLayout.setContentsMargins(0, 0, 0, 12)
        self.mainLayout.addLayout(titleLayout, 0, 0, 1, 3)
        
        self.initControler()
        self.fontSelectBtn = PushButton(self)
        self.fontLabel = HeadingLabel('Set Font', self)
        self.saveBtn = PushButton('Save', clicked=self._save)
        self.saveBtn.setObjectName('saveBtn')
        # self.saveBtn.setFont(SpinBox.leFont)
        
        self.fontSelectBtn.setFixedHeight(30)
        # self.saveBtn.setFixedHeight(30)
        SpinBox.setDefaultSettings(self.saveBtn)
        self.saveBtn.setDefault(True)
        # self.saveBtn.clicked.connect(self.save)
        # self.fontLabel.setWordWrap(True)
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
        # self.mainLayout.addWidget(aboutBtn, row, 2, Qt.AlignRight)
        
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
            #! update icon
    
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
            
            def isValid(self):
                return 
            
            def get(self):
                if self.level == None:
                    return None
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
            Setting.LowColor: ('Low Battery', Level(Setting.LowBatteryLevel)),
            Setting.CriticalColor: ('Critical Battery', Level(Setting.CriticalLevel)),
            Setting.NormalColor: ('Normal Battery', Level(Setting.NormalBatteryLevels)),
            Setting.FullBatteryLevel: ('Full Battery', Level(Setting.FullBatteryLevel)),
            Setting.OnChargingColor: ('On Charging', Level()),
            
        }

        self.colorBtnGroup = QButtonGroup(self)
        self.LEGroup = {}
            
        for row, (mem, (lb, level)) in enumerate(LBDict.items(), row+1):

            #* Labels
            lb = HeadingLabel(lb, self)
            # lb.setFont(lbFont)
            self.mainLayout.addWidget(lb, row, 0)
            
            #* Color Buttons
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
                # btn.setText('No Color')
                btn.setIcon(QIcon(r":immiApplication/icon/fullBattery.svg"))
                btn.setFont(SpinBox.leFont)

            self.setBtnColor(btn, color)
            self.mainLayout.addWidget(btn, row, 1)

            
            #* LineEdit
            
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

        
        del LBDict
        del lb
        del btn
        del le
        del mem
        del level
        del color
        del Level
        del col
        del row
    
    def _onColorBtnClicked(self, btn: QPushButton):
        color = QColorDialog.getColor(QColor(btn.Type.v), self, self.windowTitle())
        self.setBtnColor(btn, color)
        btn._color = color # use when save
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
            else:
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
    # enable dpi scale
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)
    
    pgIcon = QIcon(":immiApplication/power_traycon.png")
    windowTitle = "Power TrayCon"
    
    try:
        if BatteryStatus._hasBattery() and BatteryStatus.get_state()[1]>=0:
            os.chdir(os.path.dirname(sys.executable))
            
            dataFolder = Path('data')
            historyFolder = dataFolder/ 'history'
            settingPath = dataFolder/'data.json'
            # dataFolder.mkdir(parents=True, exist_ok=True)
            historyFolder.mkdir(parents=True, exist_ok=True)

            normalSettings = Setting.toDict() # for reset to default
            Setting.fromDict(JsonManager.readData())
            
            getFontWeightL = lambda i=int():'bold' if i==75 else 'normal'

            w = Demo()
            w.hide()
            w.systemTrayIcon.sendMessage.emit(w.systemTrayIcon.batteryChecker.previousState)
            w.secondHand.setBatterySaverCmd()
            setAutoStartUp(windowTitle)

        else:
            sticon = QSystemTrayIcon()
            sticon.setIcon(pgIcon)
            sticon.show()
            sticon.showMessage(f'Battery Error', f'"{windowTitle}"\nThis device does not come equipped with a battery', getToastIcon(pgIcon))
            sticon.showMessage(f'Battery Error', f'"{windowTitle}"\nThis device does not come equipped with a battery', getToastIcon(pgIcon))
            QTimer.singleShot(2000, sys.exit)

    except Exception as e:
        with open(r"E:\my programms\batteryPercentageTrayIcon\PowerTrayCon.log", '+a') as file:
            file.write(f'{QTime.currentTime()} {sys.executable} {os.getcwd()}\n{e}')
        raise e
    app.exec_()