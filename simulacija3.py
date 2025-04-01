# PROJEKTNI ZADATAK IZ PRAKTIKUMA IZ MERNO-AKVIZICIONIH SISTEMA
# Naziv projekta: Simulator bespilotne letelice
# Autori: Viktor Curcic, Andrej Sestic
# Datum izrade: 1.7.2024.
# Source code: Python 3.8.10

import sys
import time
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal
import serial
import matplotlib.pyplot as plt

class FlightSimulationThread(QThread): # Klasa koja izvrsava funkciju simulacije letenja
    dataReceived = pyqtSignal(float, float)  #Primaju se dva podatka tipa float - pitch i roll ugao

    def __init__(self, arduino):
        super().__init__()
        self.arduino = arduino
        self.recording = False

    def run(self):
        self.recording = True
        while self.recording:
            try:
                data = self.arduino.readline().decode().strip()
                if data:
                    pitch, roll = map(float, data.split(','))
                    self.dataReceived.emit(pitch, roll)
                time.sleep(0.1)
            except serial.SerialException: #Provera da li ima greske u primanju podataka
                print("Arduino iskljucen.")
                self.recording = False
                self.dataReceived.emit(None, None)
            except Exception as e:
                print(f"Greska u citanju podataka: {e}")
                self.recording = False

    def stop(self):
        self.recording = False

class JetSimulatorApp(QWidget): #Klasa za interfejs i kalibraciju 
    def __init__(self):
        super().__init__()
        self.initUI()
        try:
            self.arduino = serial.Serial('COM9', 9600)
        except serial.SerialException:
            QMessageBox.critical(self, "Greska", "Nemoguce povezivanje sa Arduinom.") #Izbacuje se exception ako Arduino nije povezan
            sys.exit(1)
            
        self.voltages = {'X': {'positive': None, 'negative': None},
                         'Y': {'positive': None, 'negative': None},
                         'Z': {'positive': None, 'negative': None}}
        self.recorded_data = []

    def initUI(self):
        self.setWindowTitle("Simulator bespilotne letelice")

        self.layout = QVBoxLayout()

        self.name_label = QLabel("Ime i prezime operatora")
        self.layout.addWidget(self.name_label)

        self.name_entry = QLineEdit()
        self.layout.addWidget(self.name_entry)

        self.calibrate_button = QPushButton("Zapocni kalibraciju")
        self.calibrate_button.clicked.connect(self.show_calibration_buttons)
        self.layout.addWidget(self.calibrate_button)

        self.fly_button = QPushButton("Zapocni letenje")
        self.fly_button.clicked.connect(self.start_flying)
        self.layout.addWidget(self.fly_button)

        self.end_button = QPushButton("Iskljuci")
        self.end_button.clicked.connect(self.end_program)
        self.layout.addWidget(self.end_button)

        self.calibration_layout = QVBoxLayout()

        self.setLayout(self.layout)

    def show_calibration_buttons(self):
        if not self.name_entry.text().strip():
            QMessageBox.warning(self, "Greska", "Ime i prezime operatora ne sme biti prazno.") #Ako je polje za ime i prezime prazno, izbacuje se greska
            return

        self.calibrate_x_button = QPushButton("x-osa")
        self.calibrate_x_button.clicked.connect(self.calibrate_x)
        self.calibration_layout.addWidget(self.calibrate_x_button)

        self.calibrate_y_button = QPushButton("y-osa")
        self.calibrate_y_button.clicked.connect(self.calibrate_y)
        self.calibration_layout.addWidget(self.calibrate_y_button)

        self.calibrate_z_button = QPushButton("z-osa")
        self.calibrate_z_button.clicked.connect(self.calibrate_z)
        self.calibration_layout.addWidget(self.calibrate_z_button)

        self.end_calibration_button = QPushButton("Obustavi kalibraciju")
        self.end_calibration_button.clicked.connect(self.end_calibration)
        self.calibration_layout.addWidget(self.end_calibration_button)

        self.layout.addLayout(self.calibration_layout)

    #funkcija salje signal na Arduino 
    #zavisno od toga koja se osa kalibrira, poziva exception ako Arduino nije ukljucen
    def safe_arduino_write(self, command):  
        try:
            self.arduino.write(command)
        except serial.SerialException:
            QMessageBox.critical(self, "Greska", "Arduino iskljucen.")
            self.end_program()
        except Exception as e:
            QMessageBox.critical(self, "Greska", f"Neocekivana greska: {e}")
            self.end_program()

    #funkcija koja cita output sa Arduina
    #baca exception ako dodje do greske prilikom citanja podataka
    def safe_arduino_readline(self):
        try:
            return self.arduino.readline().decode().strip()
        except serial.SerialException:
            QMessageBox.critical(self, "Greska", "Arduino iskljucen.")
            self.end_program()
        except Exception as e:
            QMessageBox.critical(self, "Greska", f"Neocekivana greska: {e}")
            self.end_program()
        return None

    def calibrate_x(self):
        self.safe_arduino_write(b'X')
        self.get_voltage('X')

    def calibrate_y(self):
        self.safe_arduino_write(b'Y')
        self.get_voltage('Y')

    def calibrate_z(self):
        self.safe_arduino_write(b'Z')
        self.get_voltage('Z')

    def get_voltage(self, axis):
        try:
            voltage_positive = float(self.safe_arduino_readline())
            voltage_negative = float(self.safe_arduino_readline())
            if len(str(voltage_positive)) < 3 or len(str(voltage_negative)) < 3:
                raise ValueError("Nedovoljno podataka ocitano.") #Ako nije ocitano ukupno 6 vrednosti napona (dva za po tri ose) dolazi do greske
            self.voltages[axis]['positive'] = voltage_positive
            self.voltages[axis]['negative'] = voltage_negative
        except ValueError as e:
            QMessageBox.critical(self, "Greska", str(e))

    def end_calibration(self):
        try:
            results = {}
            for axis in ['X', 'Y', 'Z']:
                v_pos = self.voltages[axis]['positive']
                v_neg = self.voltages[axis]['negative']
                if v_pos is None or v_neg is None:
                    raise ValueError(f"Kalibracija za {axis}-osu je nepotpuna.") #Ako neka osa nije kalibrirana, korisnik se poziva da zavrsi kalibraciju
                k = (9.81 - (-9.81)) / (v_pos - (-v_neg))
                n = 9.81 - k * v_pos
                results[axis] = {'k': k, 'n': n}

            name = self.name_entry.text().replace(" ", "_")
            with open(f"{name}.txt", "w") as file:
                file.write(f"{name}\n")
                for axis, params in results.items():
                    file.write(f"{axis}-osa: k = {params['k']}, n = {params['n']}\n")

            for i in reversed(range(self.calibration_layout.count())):
                widget = self.calibration_layout.itemAt(i).widget()
                if widget:
                    widget.setParent(None)

            self.adjustSize()
        except ValueError as e:
            QMessageBox.critical(self, "Greska", str(e))

    def start_flying(self):
        # Ako je polje za ime i prezime prazno, dolazi do greske
        if not self.name_entry.text().strip(): 
            QMessageBox.warning(self, "Greska", "Ime i prezime operatora ne sme biti prazno.")
            return

        self.safe_arduino_write(b'F')
        self.recorded_data = []
        self.fly_button.setText("Zaustavi letenje")
        self.fly_button.clicked.disconnect()
        self.fly_button.clicked.connect(self.stop_flying)
        
        # Zapocinje se simulacija letenja u posebnoj niti
        self.flight_thread = FlightSimulationThread(self.arduino)
        self.flight_thread.dataReceived.connect(self.update_flight_data)
        self.flight_thread.start()

    def update_flight_data(self, pitch, roll):
        if pitch is None or roll is None:
            QMessageBox.critical(self, "Greska", "Arduino iskljucen.")
            self.stop_flying()
            return
        self.recorded_data.append((time.time(), pitch, roll))

    def stop_flying(self):
        self.safe_arduino_write(b'S')
        self.flight_thread.stop()
        self.flight_thread.wait()
        self.fly_button.setText("Zapocni letenje")
        self.fly_button.clicked.disconnect()
        self.fly_button.clicked.connect(self.start_flying)
        self.show_plot_button()

    # Poziva se dugme za crtanje grafika
    def show_plot_button(self):
        self.plot_button = QPushButton("Nacrtaj")
        self.plot_button.clicked.connect(self.plot_data)
        self.layout.addWidget(self.plot_button)
        self.adjustSize()

    def plot_data(self):
        # Prijavljuje se greska ukoliko nema zabelezenih podataka
        if not self.recorded_data:
            QMessageBox.warning(self, "Greska", "Nema podataka.")
            return

        times = [data[0] for data in self.recorded_data]
        pitches = [data[1] for data in self.recorded_data]
        rolls = [data[2] for data in self.recorded_data]

        plt.figure(figsize=(10, 5))

        plt.subplot(2, 1, 1)
        plt.plot(times, pitches, label="Pitch")
        plt.xlabel("Time (s)")
        plt.ylabel("Pitch (°)")
        plt.legend()

        plt.subplot(2, 1, 2)
        plt.plot(times, rolls, label="Roll")
        plt.xlabel("Time (s)")
        plt.ylabel("Roll (°)")
        plt.legend()

        plt.tight_layout()
        plt.show()

    def end_program(self):
        try:
            self.arduino.close()
        except Exception:
            pass
        self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = JetSimulatorApp()
    ex.show()
    sys.exit(app.exec_())