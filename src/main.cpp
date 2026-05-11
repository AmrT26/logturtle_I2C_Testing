#include <Arduino.h>


const int SDA_PIN = 18;  // SDA Pin
const int SCL_PIN = 19;  // SCL Pin

// clock at 2kHz
// Period = 1/2000 = 500µs
// Half-period = 250µs
const int HALF_PERIOD_US = 250;


void sda_high() {
  // Release SDA → pull-up pulls to HIGH
  // INPUT = high impedance = open drain
  pinMode(SDA_PIN, INPUT);
}

void sda_low() {
  // Pull SDA to GND
  // OUTPUT + LOW = open drain active
  pinMode(SDA_PIN, OUTPUT);
  digitalWrite(SDA_PIN, LOW);
}

void scl_high() {
  // Release SCL → pull-up pulls to HIGH
  pinMode(SCL_PIN, INPUT);
  // Wait for SCL to go high
  // (clock stretching possible)
  delayMicroseconds(HALF_PERIOD_US);
}

void scl_low() {
  // Pull SCL to GND
  pinMode(SCL_PIN, OUTPUT);
  digitalWrite(SCL_PIN, LOW);
  delayMicroseconds(HALF_PERIOD_US);
}

int read_sda() {
  // Read the current state of SDA
  pinMode(SDA_PIN, INPUT);
  return digitalRead(SDA_PIN);
}


// Start and Stop CONDITIONS


void i2c_start() {
  // START condition :
  // SDA falls while SCL is HIGH

  sda_high();
  scl_high();
  delayMicroseconds(HALF_PERIOD_US);

  sda_low();   // SDA fall first
  delayMicroseconds(HALF_PERIOD_US);

  scl_low();   // SCL fall next
  delayMicroseconds(HALF_PERIOD_US);

  Serial.println("START generated");
}

void i2c_stop() {
  // STOP condition :

  sda_low();
  scl_high();
  delayMicroseconds(HALF_PERIOD_US);

  sda_high();  // SDA rise → STOP
  delayMicroseconds(HALF_PERIOD_US);

  Serial.println("STOP generated");
}


// SENDING A BIT
// Synchronized with the clock


void i2c_write_bit(int bit) {
  // 1. SCL low → we prepare SDA
  scl_low();

  // 2. Adjust SDA according to the bit
  if(bit) {
    sda_high();  // bit = 1
  } else {
    sda_low();   // bit = 0
  }

  delayMicroseconds(HALF_PERIOD_US);

  // 3. SCL high → slave reads SDA here
  scl_high();
  // SDA must be stable during SCL high

  // 4. SCL low → end of bit
  scl_low();
}


// READING A BIT (for ACK/NACK)


int i2c_read_bit() {
  // 1. SCL low → release SDA
  //    so that the slave can write
  scl_low();
  sda_high();  // release SDA
  delayMicroseconds(HALF_PERIOD_US);

  // 2. SCL high → read SDA
  scl_high();
  int bit = read_sda();  // read here

  // 3. SCL low → end
  scl_low();

  return bit;
}


// SEND A BYTE (8 bits)
// MSB first


void i2c_write_byte(byte data) {
  Serial.print("  Writing byte: 0b");
  Serial.print(data, BIN);
  Serial.print(" (0x");
  Serial.print(data, HEX);
  Serial.println(")");

  // Send the 8 bits
  // from the most significant (bit7)
  // to the least significant (bit0)
  for(int i = 7; i >= 0; i--) {
    int bit = (data >> i) & 0x01;
    i2c_write_bit(bit);
    Serial.print(bit);  // afficher chaque bit
  }
  Serial.println();
}


// READ ACK OR NACK
// After each byte sent
// the slave must respond :
// ACK  = SDA LOW  (0) → everything is fine
// NACK = SDA HIGH (1) → problem


bool i2c_read_ack() {
  int ack_bit = i2c_read_bit();

  if(ack_bit == 0) {
    Serial.println("  → ACK  (slave responded)");
    return true;   // ACK
  } else {
    Serial.println("  → NACK (no response)");
    return false;  // NACK
  }
}


// SEND A COMPLETE I2C FRAME


void i2c_send_frame(byte address, byte data) {
  Serial.println("==============================");
  Serial.print("Frame: START | 0x");
  Serial.print(address, HEX);
  Serial.print(" | 0x");
  Serial.print(data, HEX);
  Serial.println(" | STOP");
  Serial.println("==============================");

  // 1. START
  i2c_start();

  // 2. Adresse + bit W (0 = writting)
  // the adresse is on 7 bits
  // On décale à gauche et on ajoute W=0
  Serial.println("Sending address + W:");
  byte addr_byte = (address << 1) | 0x00;
  i2c_write_byte(addr_byte);

  // 3. Lire ACK de l'adresse
  bool ack1 = i2c_read_ack();

  // 4. Envoyer la donnée
  if(ack1) {
    Serial.println("Sending data:");
    i2c_write_byte(data);

    // 5. Lire ACK de la donnée
    i2c_read_ack();
  }

  // 6. STOP
  i2c_stop();
  Serial.println("==============================");
}


// INTERACTIVE INTERFACE


// global variables to store
// the adress and data chosen
byte current_address = 0x50;  // default
byte current_data    = 0xAB;  // default

void printMenu() {
  Serial.print  (" Current address : 0x");
  Serial.println(current_address, HEX);
  Serial.print  (" Current data    : 0x");
  Serial.print  (current_data, HEX);
  Serial.print  (" (0b");
  Serial.print  (current_data, BIN);
  Serial.println(")");
  Serial.println("------------------------------");
  Serial.println(" Commands:");
  Serial.println("   t      → Send current frame");
  Serial.println("   l      → Loop (continuous)");
  Serial.println("   a 0x50 → Set address");
  Serial.println("   d 0xAB → Set data");
  Serial.println("   s      → Scan I2C bus");
  Serial.println("   h      → Help");
  Serial.println("==============================");
}

// Parse a hexadecimal number
// from a string
// ex: "0x50" or "50" → 80
byte parseHex(String str) {
  str.trim();   // Remove whitespace
  // Remove "0x" if present
  if(str.startsWith("0x") || str.startsWith("0X")) {
    str = str.substring(2);
  }
  // Convert to number
  return (byte)strtol(str.c_str(), NULL, 16);
}

// Scan the I2C bus
void scanBus() {
  Serial.println("=== Scanning I2C bus ===");
  int found = 0;
  for(byte addr = 1; addr < 127; addr++) {
    i2c_start();
    byte addr_byte = (addr << 1) | 0x00;
    i2c_write_byte(addr_byte);
    
    // Read ACK without displaying
    scl_low();
    sda_high();
    delayMicroseconds(HALF_PERIOD_US);
    scl_high();
    int ack = read_sda();
    scl_low();
    i2c_stop();
    
    if(ack == 0) {
      Serial.print("  Found device at: 0x");
      if(addr < 16) Serial.print("0");
      Serial.println(addr, HEX);
      found++;
    }
  }
  if(found == 0) {
    Serial.println("  No devices found");
    Serial.println("  (NACK expected from AD3)");
  }
  Serial.println("========================");
}

// SETUP

void setup() {
  Serial.begin(115200);
  delay(1000);

  sda_high();
  scl_high();

  printMenu();
}


// LOOP


void loop() {
  if(Serial.available()) {
    
    // Read the complete command
    String input = Serial.readStringUntil('\n');
    input.trim();
    
    // Extract the command (first character)
    char cmd = input.charAt(0);
    
    // Extract the parameter (after the first space)
    String param = "";
    if(input.length() > 2) {
      param = input.substring(2);
    }

    switch(cmd) {

      // Send the current frame
      case 't':
        i2c_send_frame(current_address, current_data);
        break;

      // Loop continuously
      case 'l':
        Serial.println("Loop... tap any key to stop");
        while(!Serial.available()) {
          i2c_send_frame(current_address, current_data);
          delay(100);
        }
        Serial.read(); // empty the buffer
        break;

      // Change the address
      // ex: taper "a 0x71"
      case 'a':
        if(param.length() > 0) {
          current_address = parseHex(param);
          Serial.print("Address set to: 0x");
          Serial.println(current_address, HEX);
        } else {
          Serial.println("Usage: a 0x50");
        }
        break;

      // Change the data
      // ex: taper "d 0xAB"
      case 'd':
        if(param.length() > 0) {
          current_data = parseHex(param);
          Serial.print("Data set to: 0x");
          Serial.print(current_data, HEX);
          Serial.print(" (0b");
          Serial.print(current_data, BIN);
          Serial.println(")");
        } else {
          Serial.println("Usage: d 0xAB");
        }
        break;

      // Scan the bus
      case 's':
        scanBus();
        break;

      // Help
      case 'h':
        printMenu();
        break;

      default:
        Serial.println("Unknown command - type 'h' for help");
        break;
    }
  }
}