/* PROJEKTNI ZADATAK IZ PRAKTIKUMA IZ MERNO-AKVIZICIONIH SISTEMA
   Naziv projekta: Simulator bespilotne letelice
   Autori: Viktor Curcic, Andrej Sestic
   Datum izrade: 1.7.2024.
   Source code: Arduino IDE 2.3.2*/

#include <TM1637Display.h>
#include <TimerOne.h>


#define CLK 9
#define DIO 8
#define TOUCH_SENSOR 2
#define X_AXIS A0
#define Y_AXIS A1
#define Z_AXIS A2
#define RED_LED 3
#define GREEN_LED 11

TM1637Display display(CLK, DIO);

enum Axis { NONE, X, Y, Z };
Axis currentAxis = NONE;

volatile bool touchDetected = false;
bool calibrating = false;
bool flying = false;
float positiveVoltage = 0;
float negativeVoltage = 0;

void setup() {
  Serial.begin(9600);
  pinMode(TOUCH_SENSOR, INPUT);
  attachInterrupt(digitalPinToInterrupt(TOUCH_SENSOR), touchSensorISR, RISING); // Definise se interrupt za kapacitivni senzor dodira
  Timer1.initialize(100000); // Definise se citanje napona na svakih 100ms
  Timer1.attachInterrupt(readVoltageISR);
  display.setBrightness(0x0f);
  pinMode(RED_LED, OUTPUT);
  pinMode(GREEN_LED, OUTPUT);
}

void loop() {
  if (Serial.available() > 0) {
    char command = Serial.read(); // Cita se uneta komanda i zavisno od nje se zapocinje kalibracija ili letenje
    if (command == 'X') {
      startCalibration(X);
    } else if (command == 'Y') {
      startCalibration(Y);
    } else if (command == 'Z') {
      startCalibration(Z);
    } else if (command == 'F') {
      startFlying();
    } else if (command == 'S') {
      stopFlying();
    }
  }

  if (calibrating) {
    float voltage = readVoltage(currentAxis);
    displayVoltage(voltage);
    if (touchDetected) {
      touchDetected = false;
      if (positiveVoltage == 0) {
        positiveVoltage = voltage;
        delay(500); // Kasnjenje za debaunsiranje senzora
      } else {
        negativeVoltage = voltage;
        calibrating = false;
        sendVoltageData(); // Funkcija koja salje podatke u Python okruzenje
      }
    }
  }

  if (flying) {
    int x = analogRead(X_AXIS); 
    delay(1); //
    int y = analogRead(Y_AXIS); 
    delay(1); 
    int z = analogRead(Z_AXIS); 

    float zero_G = 512.0; 
    float scale = 102.3; 

    double ax = ((float)x - 331.5)/65*9.81; 
    double ay = ((float)y - 329.5)/68.5*9.81; 
    double az = ((float)z - 340)/68*9.81; 

    float pitch = atan2(ax, sqrt(ay*ay + az*az)) * 180 / PI;
    float roll = atan2(ay, sqrt(ax*ax + az*az)) * 180 / PI;

    if (pitch < 0) {
      analogWrite(RED_LED, map(abs(pitch), 0, 90, 0, 255)); // Vrsi se menjanje intenziteta boje crvene diode zavisno od vrednosti ugla
      analogWrite(GREEN_LED, 0);
    } else {
      analogWrite(GREEN_LED, map(pitch, 0, 90, 0, 255)); // Vrsi se menjanje intenziteta boje zelene diode zavisno od vrednosti ugla
      analogWrite(RED_LED, 0);
    }

    display.showNumberDec(abs(pitch), false);
    Serial.print(pitch);
    Serial.print(",");
    Serial.println(roll);
    delay(100);
  }
}

void startCalibration(Axis axis) {
  currentAxis = axis;
  calibrating = true;
  positiveVoltage = 0;
  negativeVoltage = 0;
}

void startFlying() {
  flying = true;
}

void stopFlying() {
  flying = false;
  analogWrite(RED_LED, 0);
  analogWrite(GREEN_LED, 0);
}

void touchSensorISR() {
  touchDetected = true;
}

void readVoltageISR() {
}

// Cita se napon sa one ose koja je odabrana
float readVoltage(Axis axis) {
  int analogPin;
  switch (axis) {
    case X:
      analogPin = X_AXIS;
      break;
    case Y:
      analogPin = Y_AXIS;
      break;
    case Z:
      analogPin = Z_AXIS;
      break;
    default:
      return 0;
  }
  int sensorValue = analogRead(analogPin);
  return (sensorValue * 5.0) / 1023.0;
}

// Funkcija za prikaz napona na displeju
void displayVoltage(float voltage) {
  int displayValue = voltage * 100;
  display.showNumberDec(displayValue, false);
}

void sendVoltageData() {
  Serial.println(positiveVoltage, 4);
  Serial.println(negativeVoltage, 4);
}