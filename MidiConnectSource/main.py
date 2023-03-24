import time
from datetime import timedelta
import sys
import os

from PyQt5.QtCore import QSize, QThread, QObject, pyqtSignal, Qt
from PyQt5.QtWidgets import *
from PyQt5 import QtGui
import mido
from mido import MidiFile
import pynput
import mido.backends.rtmidi
kb = pynput.keyboard
keyboard = kb.Controller()

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


class Worker(QObject):
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
                try:
                    with mido.open_input(Selected) as inport:
                        for msg in inport:
                            ProcessMsg(msg)
                except:
                    print("Error")
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

def ProcessMsg(msg):
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
    pass