import time
from datetime import timedelta
import sys
import os

from PyQt5.QtCore import QSize, QThread, QObject, pyqtSignal, Qt
from PyQt5.QtWidgets import *
from PyQt5 import QtGui
import mido
from mido import MidiFile
import math
import mido.backends.rtmidi
# import pydirectinput
import platform
import pynput
kb = pynput.keyboard
keyboard=kb.Controller()
ConnectThread = QThread()
PlayThread = QThread()
ProgressThread = QThread()
app = None
DeleteConnection = None
ShouldStop = False
ShouldPause = False
FilePlay = None
FilePause = None
FileStop = None
SelectedMidiFile = None
FileDurationLabel = None
FileProgressBar = None
FileSelectButton = None
start_time = None
playback_time = 0
total_pause = 0
LengthString = None
SelectedMidiPort = None

# Will be used to later on determine which dict to use in vk_keycodes
CurrentPlatform = platform.system()

# To be used when encoding octave, note, velocity, control 
encoded_keys = ['numpad0', 'numpad1', 'numpad2', 'numpad3', 'numpad4', 'numpad5', 'numpad6', 'numpad7', 'numpad8', 'numpad9', 'subtract', 'add']

# Maps the virtual keycodes for each OS
vk_keycodes = {
    #https://learn.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes?redirectedfrom=MSDN
    "Windows": {
        "numpad0": 0x52,
        "numpad1": 0x4F,
        "numpad2": 0x50,
        "numpad3": 0x51,
        "numpad4": 0x4B,
        "numpad5": 0x4C,
        "numpad6": 0x4D,
        "numpad7": 0x47,
        "numpad8": 0x48,
        "numpad9": 0x49,
        "subtract": 0x4A,
        "add": 0x4E,
        "multiply": 0x37,
    },

    #Retrieved from a debian based distro running on an X server
    #xmodmap -pke
    #xev
    #https://github.com/torvalds/linux/blob/master/include/uapi/linux/input-event-codes.h
    "Linux": {
        "numpad0": 0xffb0,
        "numpad1": 0xffb1,
        "numpad2": 0xffb2,
        "numpad3": 0xffb3,
        "numpad4": 0xffb4,
        "numpad5": 0xffb5,
        "numpad6": 0xffb6,
        "numpad7": 0xffb7,
        "numpad8": 0xffb8,
        "numpad9": 0xffb9,
        "subtract": 0xffad,
        "add": 0xffab,
        "multiply": 0xffaa,
    },

    # https://github.com/phracker/MacOSX-SDKs/blob/master/MacOSX11.3.sdk/System/Library/Frameworks/Carbon.framework/Versions/A/Frameworks/HIToolbox.framework/Versions/A/Headers/Events.h
    # https://stackoverflow.com/questions/3202629/where-can-i-find-a-list-of-mac-virtual-key-codes/16125341#16125341
    #Aka macOS(Do not change as this is the value expected and returned platform.system())
    "Darwin": {
        "numpad0": 0x52,
        "numpad1": 0x53,
        "numpad2": 0x54,
        "numpad3": 0x55,
        "numpad4": 0x56,
        "numpad5": 0x57,
        "numpad6": 0x58,
        "numpad7": 0x59,
        "numpad8": 0x5B,
        "numpad9": 0x5C,
        "subtract": 0x4E,
        "add": 0x45,
        "multiply": 0x43,
    }
}


# class Keys:
#     NUM0 = 'numpad0'
#     NUM1 = 'numpad1'
#     NUM2 = 'numpad2'
#     NUM3 = 'numpad3'
#     NUM4 = 'numpad4'
#     NUM5 = 'numpad5'
#     NUM6 = 'numpad6'
#     NUM7 = 'numpad7'
#     NUM8 = 'numpad8'
#     NUM9 = 'numpad9'
# pydirectinput.PAUSE = 0
# pydirectinput.KEYBOARD_MAPPING[Keys.NUM0] = 0x52
# pydirectinput.KEYBOARD_MAPPING[Keys.NUM1] = 0x4F
# pydirectinput.KEYBOARD_MAPPING[Keys.NUM2] = 0x50
# pydirectinput.KEYBOARD_MAPPING[Keys.NUM3] = 0x51
# pydirectinput.KEYBOARD_MAPPING[Keys.NUM4] = 0x4B
# pydirectinput.KEYBOARD_MAPPING[Keys.NUM5] = 0x4C
# pydirectinput.KEYBOARD_MAPPING[Keys.NUM6] = 0x4D
# pydirectinput.KEYBOARD_MAPPING[Keys.NUM7] = 0x47
# pydirectinput.KEYBOARD_MAPPING[Keys.NUM8] = 0x48
# pydirectinput.KEYBOARD_MAPPING[Keys.NUM9] = 0x49


class Worker2(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(float)
    def run(self):
        print("Thread 2 Start")
        global playback_time
        global start_time
        global LengthString
        global ShouldStop
        global ShouldPause
        while ShouldStop is False:
            if SelectedMidiFile is not None and not ShouldPause and start_time is not None:
                playback_time = time.time() - start_time - total_pause
                #self.progress.emit(playback_time)
            time.sleep(0.2)
        print("Thread 2 Finished")
        self.finished.emit()


class Worker(QObject): # Handles running Midi Files
    finished = pyqtSignal()
    progress = pyqtSignal(int)

    def run(self):
        print("Thread 1 Start")
        global start_time
        global total_pause
        global ShouldStop
        global ShouldPause
        start_time = time.time()
        input_time = 0.0
        total_pause = 0.0
        global SelectedMidiFile
        for msg in SelectedMidiFile:

            if ShouldPause:
                print("Pausing Midi")
                PauseStart = time.time()
                while True:
                    time.sleep(0.1)
                    if ShouldPause == False:
                        print("Breaking")
                        break
                time.sleep(0.2)
                print("Unpausing Midi")
                total_pause = total_pause + (time.time()-PauseStart)
            if ShouldStop:
                break
            modifiedmsgtime = msg.time
            if modifiedmsgtime > 10:
                modifiedmsgtime = 10

            input_time += modifiedmsgtime
            global playback_time
            playback_time = time.time() - start_time - total_pause
            duration_to_next_event = input_time - playback_time

            if duration_to_next_event > 0.0:
                time.sleep(duration_to_next_event)
            if ShouldStop:
                break
            if not msg.is_meta:
                ProcessMsg(msg)
            continue

        print("Thread 1 Finished")
        self.finished.emit()

class Worker3(QObject): # Handles MIDI input from an input port
    finished = pyqtSignal()
    progress = pyqtSignal(int)

    def run(self):
        print("Thread 3 Start")
        global SelectedMidiPort
        try:
            with mido.open_input(SelectedMidiPort) as inport:
                for msg in inport:
                    ProcessMsg(msg)
        except:
            print("Error")

        print("Thread 1 Finished")
        self.finished.emit()

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QtGui.QIcon('favicon.ico'))
        self.setWindowTitle("MidiConnect - ©2023 LordHenryVonHenry")

        FileSelectLabel = QLabel()
        FileSelectLabel.setText("Midi File")
        global FileSelectButton
        FileSelectButton = QPushButton("Select File")
        FileSelectButton.setFocusPolicy(Qt.NoFocus)
        def SelectMidi(self):
            options =QFileDialog.Options()
            #options |= QFileDialog.DontUseNativeDialog
            fileName, _ = QFileDialog.getOpenFileName(app,"QFileDialog.getOpenFileName()", "","Midi Files (*.mid)", options=options)
            print(fileName)
            if fileName:
                print(fileName)
                FileSelectedLabel.setText(os.path.basename(fileName))
                global SelectedMidiFile
                SelectedMidiFile = MidiFile(fileName)
                PositionString = "00:00"
                m, s = divmod(SelectedMidiFile.length, 60)
                m = int(m)
                s = int(s)
                global LengthString
                LengthString = "{:02d}:{:02d}".format(m,s)
                FileDurationLabel.setText(PositionString+"/"+LengthString)
                FileStop.setEnabled(False)
                FilePause.setEnabled(False)
                FilePlay.setEnabled(True)
                global DeleteConnection
                DeleteConnection = PlayMidi
            pass
        FileSelectButton.clicked.connect(SelectMidi)
        FileSelectedLabel = QLabel()
        FileSelectedLabel.setText("")
        global FilePlay
        global FilePause
        global FileStop
        FilePlay = QPushButton("Play")
        FilePlay.setFocusPolicy(Qt.NoFocus)

        def PlayMidi():
            global DeleteConnection
            print("Play Button")
            global ShouldPause
            if ShouldPause:

                DeleteConnection = PauseMidi
                FilePlay.setEnabled(False)
                FilePause.setEnabled(True)
                FileStop.setEnabled(True)
                ShouldPause = False
                return
            FileSelectButton.setEnabled(False)
            global ShouldStop
            ShouldStop = False
            ShouldPause = False
            DeleteConnection=PauseMidi
            print("Playing "+FileSelectedLabel.text())
            FilePlay.setEnabled(False)
            FilePause.setEnabled(True)
            FileStop.setEnabled(True)

            self.thread = PlayThread
            self.worker = Worker()
            self.worker.moveToThread(self.thread)
            self.thread.started.connect(self.worker.run)
            self.worker.finished.connect(self.thread.quit)
            self.worker.finished.connect(self.worker.deleteLater)

            def ThreadFinished():
                print("Thread Finished")
                ShouldStop = True
                FilePlay.setEnabled(True)
                FilePause.setEnabled(False)
                FileStop.setEnabled(False)
                PositionString = "00:00"
                m, s = divmod(SelectedMidiFile.length, 60)
                m = int(m)
                s = int(s)
                global LengthString
                LengthString = "{:02d}:{:02d}".format(m, s)
                FileDurationLabel.setText(PositionString + "/" + LengthString)
                FileProgressBar.setValue(0)
                FileSelectButton.setEnabled(True)

            self.worker.finished.connect(ThreadFinished)
            #self.thread.finished.connect(self.thread.deleteLater)

            self.thread.start()

            self.thread2 = ProgressThread
            self.worker2 = Worker2()
            self.worker2.moveToThread(self.thread2)
            self.thread2.started.connect(self.worker2.run)
            def UpdateProgress(Progress):
                #print("Update Progress Triggered")
                m, s = divmod(Progress, 60)
                m = int(m)
                s = int(s)
                PositionString = "{:02d}:{:02d}".format(m, s)
                FileDurationLabel.setText(PositionString + "/" + LengthString)
                FileProgressBar.setValue(int((Progress / SelectedMidiFile.length) * 1000))
            self.worker2.progress.connect(UpdateProgress)
            self.worker2.finished.connect(self.thread2.quit)
            self.worker2.finished.connect(self.worker2.deleteLater)
            #self.thread2.finished.connect(self.thread2.deleteLater)
            self.thread2.start()

        FilePlay.setEnabled(False)
        FilePlay.clicked.connect(PlayMidi)
        FilePause = QPushButton("Pause")
        FilePause.setFocusPolicy(Qt.NoFocus)
        def PauseMidi():
            print("Pause Button")
            global ShouldPause
            ShouldPause = True
            global DeleteConnection
            DeleteConnection = PlayMidi
            FilePlay.setEnabled(True)
            FilePause.setEnabled(False)
            FileStop.setEnabled(True)
        FilePause.setEnabled(False)
        FilePause.clicked.connect(PauseMidi)
        FileStop = QPushButton("Stop")
        FileStop.setFocusPolicy(Qt.NoFocus)
        def StopMidi():
            print("Stop Button")
            global DeleteConnection
            DeleteConnection=PlayMidi
            global ShouldStop
            global ShouldPause
            ShouldStop = True
            ShouldPause = False
            FilePlay.setEnabled(False)
            FilePause.setEnabled(False)
            FileStop.setEnabled(False)
            FileSelectButton.setEnabled(True)
        FileStop.setEnabled(False)
        FileStop.clicked.connect(StopMidi)
        global FileDurationLabel
        FileDurationLabel = QLabel()
        FileDurationLabel.setText("00:00/00:00")
        global FileProgressBar
        FileProgressBar = QProgressBar()
        FileProgressBar.setMaximumHeight(5)
        FileProgressBar.setRange(0,1000)
        InputSelectLabel = QLabel()
        InputSelectLabel.setText("Direct Midi Input")

        InputsDropdown = QComboBox()
        InputsDropdown.addItems(mido.get_input_names())

        def RefreshInputs(self):
            print("Refreshing Inputs")
            InputsDropdown.clear()
            InputsDropdown.addItems(mido.get_input_names())
        RefreshInputsButton = QPushButton("Refresh")
        RefreshInputsButton.setFocusPolicy(Qt.NoFocus)
        RefreshInputsButton.clicked.connect(RefreshInputs)
        InputConnectButton = QPushButton("Connect")

        def ConnectInput():
            InputConnectButton.setEnabled(False)
            InputStopButton.setEnabled(True)
            Selected = InputsDropdown.currentText()
            AvailableInputs = mido.get_input_names()
            if Selected in AvailableInputs:
                print("Input Found, Connecting")
                print("Connecting to "+Selected)
                global SelectedMidiPort
                SelectedMidiPort = Selected
                self.thread3 = ConnectThread
                self.worker3 = Worker3()
                self.worker3.moveToThread(self.thread3)
                self.thread3.started.connect(self.worker3.run)
                self.worker3.finished.connect(self.thread3.quit)
                self.worker3.finished.connect(self.worker3.deleteLater)
                self.thread3.start()
                #
                #try:
                #    with mido.open_input(Selected) as inport:
                #        for msg in inport:
                #            ProcessMsg(msg)
                #except:
                #    print("Error")
            pass

        InputConnectButton.clicked.connect(ConnectInput)
        InputStopButton = QPushButton("Stop")
        def StopInput():
            InputConnectButton.setEnabled(True)
            InputStopButton.setEnabled(False)
            pass
        InputStopButton.clicked.connect(StopInput)
        InputStopButton.setEnabled(False)
        FileRow = QHBoxLayout()
        FileRow.addWidget(FileSelectLabel)
        FileRow.addWidget(FileSelectButton)
        FileRow.addWidget(FileSelectedLabel)
        FileRowContainer = QWidget()
        FileRowContainer.setLayout(FileRow)

        FileControlRow = QHBoxLayout()
        FileControlRow.addWidget(FilePlay)
        FileControlRow.addWidget(FilePause)
        FileControlRow.addWidget(FileStop)

        FileControlRowContainer = QWidget()
        FileControlRowContainer.setLayout(FileControlRow)
        InputRow = QHBoxLayout()
        layout = QVBoxLayout()
        InputRow.addWidget(InputSelectLabel)
        InputRow.addWidget(InputsDropdown)
        InputRow.addWidget(RefreshInputsButton)

        InputControlRow = QHBoxLayout()
        InputControlRow.addWidget(InputConnectButton)
        InputControlRow.addWidget(InputStopButton)
        InputControlRowContainer = QWidget()
        InputControlRowContainer.setLayout(InputControlRow)

        InputRowContainer = QWidget()
        InputRowContainer.setLayout(InputRow)
        layout.addWidget(InputRowContainer)
        layout.addWidget(InputControlRowContainer)
        layout.addWidget(QWidget())
        layout.addWidget(FileRowContainer)
        layout.addWidget(FileControlRowContainer)
        layout.addWidget(FileDurationLabel)
        layout.addWidget(FileProgressBar)
        container = QWidget()
        container.setLayout(layout)
        self.setFixedSize(QSize(400,240))
        self.setCentralWidget(container)
        self.show()


def onDel():
    print("Delete")
    if DeleteConnection is not None:
        print("Delete2")
        DeleteConnection()

def for_canonical(f):
    return lambda k: f(listener.canonical(k))

def SendKey(NumpadKeyName): #numpad0-9, -, +
    #keyboard.press(kb.KeyCode.from_vk(NumpadKeyName))
    #keyboard.release(kb.KeyCode.from_vk(NumpadKeyName))
    # Simply gets the hex vk keycode for the respective OS then sends it over to pynput
    keyboard.tap(kb.KeyCode.from_vk(vk_keycodes[CurrentPlatform][NumpadKeyName]))
    # pydirectinput.press(NumpadKeyName) # Internally calls keyDown and keyUp
    #pydirectinput.keyDown(NumpadKeyName)
    #pydirectinput.keyUp(NumpadKeyName)
def get_digit(number, n): #Redundant code
    return number // 10 ** n % 10

def EncodeAndSendMessage(a, b, c, d):
    """
        a: OctaveNo_PlusOne[floor(note / 12)] OR Control A[floor(control / 12)]
        b: NoteNo[floor(note % 12)] OR Control B[floor(control % 12)]
        c: VelocityA[floor(velocity / 12)] OR Control Value A[floor(msg.value / 12)]
        d: VelocityB[floor(velocity % 12)] OR Control Value B[floor(msg.value % 12)]
    """
    # Signifies the beginning of a midi message
    SendKey("multiply")
    print(a,b,c,d)
    SendKey(encoded_keys[a])
    SendKey(encoded_keys[b])
    
    SendKey(encoded_keys[c])
    SendKey(encoded_keys[d])

def ProcessMsg(msg):
    if msg.type == "clock":
        return
    elif msg.type == "note_on" or msg.type == "note_off":

        # We are dividing by 12 because we will be encoding it with 12 keys only(The keys are "0123456789-+")
        # Additionally, it adds up nicely because there are 12 semitones in one octave
        
        # C0 aka Note C at Octave 0
        # Note number: 12
        # O = msg.note / 12 = 12 / 12 = 1
        # Octave = 1 - O = 1 - 1 = 0
        
        # C4 aka Note C at Octave 4
        # Note number: 60
        # O = msg.note / 12 = 60 /12 = 5
        # Octave = 1 - O = 5 - 1 = 4

        # To decode
        # (DIV_VAL * 12) + MODULOS_VAL

        OctaveNo = math.floor(msg.note/12) # Gives us the octave number(begins from the 0th octave at 1)
        NoteNo = math.floor(msg.note%12) # Gives us the note number relative to the current octave(begins from the note C at 0)

        if msg.type == "note_off":
            VelocityA1 = 0
            VelocityA2 = 0 
        else:
            #Velocity has a range from 0 to 127
            VelocityA1 = math.floor(msg.velocity/12) # Same logic as OctaveNo
            VelocityA2 = math.floor(msg.velocity%12) # Same logic as NoteNo


        EncodeAndSendMessage(OctaveNo, NoteNo, VelocityA1, VelocityA2)

    elif msg.type == "control_change":
        # Uses the same logic as the previous if statement to encode a control change
        control = None
        if msg.control == 64:
            control = 143
        if control:
            a, b, c, d = math.floor(control / 12), math.floor(control % 12), math.floor(msg.value / 12), math.floor(msg.value % 12)
            EncodeAndSendMessage(a, b, c, d)
        #encoded_keys = [96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 109, 107]#110 111 cuz roblox keycodes differ
        #ToSend = [math.floor(msg.control / 12), math.floor(msg.value % 12), 0, 0]
        #keyboard.press(kb.KeyCode.from_vk(107))
        #keyboard.release(kb.KeyCode.from_vk(107))
        #for x in ToSend:
        #    keyboard.press(kb.KeyCode.from_vk(encoded_keys[x]))
        #    keyboard.release(kb.KeyCode.from_vk(encoded_keys[x]))
    

    print(f"msg: {msg}")


def ProcessMsg2(msg): # Redundant function at its current state(uses keyboard so that's interesting)
    if msg.type == "clock":
        pass
    elif msg.type == "note_on":
        keyboard.type("n" + "|" + str(msg.note) + "|" + str(msg.velocity) + "|#")
        #print("n", msg.note, msg.velocity, "#")
        pass
    elif msg.type == "note_off":
        keyboard.type("n" + "|" + str(msg.note) + "|" + "0" + "|#")
        #print("n", msg.note, msg.velocity, "#")
    elif msg.type == "control_change":
        keyboard.type("c" + "|" + str(msg.control) + "|" + str(msg.value) + "|#")
        #print("c", msg.control, msg.value, "#")
        pass
    else:
        print(msg)

def main():
    app = QApplication([])
    window = Window()
    app.exec_()
    #sys.exit(app.exec_())

if __name__ == '__main__':
    hotkey = kb.HotKey(
        kb.HotKey.parse('<delete>'),
        onDel)
    listener = kb.Listener(
        on_press=for_canonical(hotkey.press),
        on_release=for_canonical(hotkey.release))
    listener.start()
    main()