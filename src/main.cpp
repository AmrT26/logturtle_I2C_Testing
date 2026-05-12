#include <Arduino.h>
#include <Wire.h>

// ============================================
// LOGTURTLE - I2C Controller
// ============================================

byte current_address = 0x40; // Default I2C address of the chip
byte current_reg     = 0x00; // Default register index
byte current_data    = 0xAB; // Default data


// IOMUX CONFIGURATION

void config_pins_iomux() {

  // SDA Pin 18 → Push-Pull
  // Clear bit 11 (ODE = Open Drain Enable)
  // ODE = 0 → Push-Pull
  IOMUXC_SW_PAD_CTL_PAD_GPIO_AD_B1_01 &= ~(1 << 11);
  Serial.println("SDA Pin 18 → Push-Pull (IOMUX ODE=0)");

  // SCL Pin 19 → Open-Drain
  // Set bit 11 (ODE = Open Drain Enable)
  // ODE = 1 → Open-Drain
  IOMUXC_SW_PAD_CTL_PAD_GPIO_AD_B1_00 |= (1 << 11);
  Serial.println("SCL Pin 19 → Open-Drain (IOMUX ODE=1)");
}


// Write a register (address, register index, data)

void i2c_write_register(byte device_address, byte reg_index, byte data) {
  Serial.println("==============================");
  Serial.print("Address : 0x"); Serial.println(device_address, HEX);
  Serial.print("Register: 0x"); Serial.println(reg_index, HEX);
  Serial.print("Data    : 0x"); Serial.print(data, HEX);
  Serial.print(" (0b");        Serial.print(data, BIN);
  Serial.println(")");
  Serial.println("------------------------------");

  Wire.beginTransmission(device_address);
  Wire.write(reg_index);
  Wire.write(data);
  byte error = Wire.endTransmission();

  switch(error) {
    case 0:
      Serial.println("→ ACK");
      break;
    case 2:
      Serial.println("→ NACK on address");
      break;
    case 3:
      Serial.println("→ NACK on data");
      break;
    default:
      Serial.print("→ Error: ");
      Serial.println(error);
  }
  Serial.println("==============================");
}


//Read a register

void i2c_read_register(byte device_address, byte reg_index) {
  Serial.println("==============================");
  Serial.print("Reading Reg: 0x"); Serial.println(reg_index, HEX);

  // 1. First phase : sending the register index
  // We start a transmission but we don't send a STOP at the end
  Wire.beginTransmission(device_address);
  Wire.write(reg_index);
  
  // The 'false' generates a RESTART instead of a STOP
  byte error = Wire.endTransmission(false); 

  if (error != 0) {
    Serial.println("Error: Device not found or NACK");
    return;
  }

  // 2. Second phase : Request the data (Read)
  // requestFrom generates the RESTART followed by the address in read mode
  Wire.requestFrom(device_address, (uint8_t)1);

  if (Wire.available()) {
    byte data = Wire.read();
    Serial.print("Data read  : 0x"); Serial.print(data, HEX);
    Serial.print(" (0b");          Serial.print(data, BIN);
    Serial.println(")");
  }
  Serial.println("==============================");
}

// Scan I2C bus

void scanBus() {
  Serial.println("=== Scanning I2C bus ===");
  int found = 0;

  for(byte addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    byte error = Wire.endTransmission();

    if(error == 0) {
      Serial.print("  Found: 0x");
      if(addr < 16){
        Serial.print("0"); Serial.println(addr, HEX);
        found++; 
      }
    }
  }

  if(found == 0) {
    Serial.println("  No devices found");
  }
  Serial.println("========================");
}


// hexadecimal number parsing


byte parseHex(String str) {
  str.trim();
  if(str.startsWith("0x") || str.startsWith("0X")) {
    str = str.substring(2);
  }
  return (byte)strtol(str.c_str(), NULL, 16);
}


// Menu

void printMenu() {
  Serial.println("==============================");
  Serial.println(" I2C Controller - Teensy 4.1");
  Serial.println(" SDA Pin18 PP | SCL Pin19 OD");
  Serial.println(" Clock : 2kHz");
  Serial.println("==============================");
  Serial.print  (" Address : 0x");
  Serial.println(current_address, HEX);
  Serial.print(" Register: 0x");
  Serial.println(current_reg, HEX);
  Serial.print  (" Data    : 0x");
  Serial.println(current_data, HEX);
  Serial.println("------------------------------");
  Serial.println(" Commands:");
  Serial.println("   a 0x40 → Send target Address");
  Serial.println("   r 0x05 → Read Register (ex: 5)");
  Serial.println("   w 0xFE → Write current data to current Reg");
  Serial.println("   d 0xAB → Set data value to write");
  Serial.println("   i 0x00 → Set register index");
  Serial.println("   s      → Scan bus");
  Serial.println("   h      → Help");
  Serial.println("==============================");
}


// SETUP


void setup() {
  Serial.begin(115200);
  delay(1000);

  // 1. Initialising Wire.h
  Wire.begin();

  // 2. Configuring IOMUX to configure the pins as open-drain or push-pull
  config_pins_iomux();

  // 3. Clock at 2kHz
  Wire.setClock(2000);

  Serial.println("==============================");
  Serial.println(" Pin Configuration:");
  Serial.println("   Wire.begin()     → OK");
  Serial.println("   IOMUX SDA PP     → OK");
  Serial.println("   IOMUX SCL OD     → OK");
  Serial.print  ("   Clock 2kHz       → OK");
  Serial.println("==============================");

  printMenu();
}


// LOOP


void loop() {
  if(Serial.available()) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    char cmd = input.charAt(0);
    String param = "";
    if(input.length() > 2) {
      param = input.substring(2);
    }

    switch(cmd) {
      case 'a':
        if(param.length() > 0) {
          current_address = parseHex(param);
          Serial.print("Address → 0x");
          Serial.println(current_address, HEX);
        } else {
          Serial.println("Usage: a 0x71");   //shows the syntax to set the address
        }
        break;

      case 'i':
        if(param.length() > 0) {
          current_reg = parseHex(param);
          Serial.print("Register → 0x");
          Serial.println(current_reg, HEX);
        } else {
          Serial.println("Usage: i 0x05");   //shows the syntax to set the register index
        }
        break;

      case 'd':
        if(param.length() > 0) {
          current_data = parseHex(param);
          Serial.print("Data → 0x");
          Serial.print(current_data, HEX);
          Serial.print(" (0b");
          Serial.print(current_data, BIN);
          Serial.println(")");
        } else {
          Serial.println("Usage: d 0xAB");  //shows the syntax to set the data
        }
        break;
      
      case 'r': //Reading a register
        if(param.length() > 0){
          current_reg = parseHex(param);
        }
        i2c_read_register(current_address, current_reg);
        break;

      case 'w': //Writing to a register
        if(param.length() > 0){
          current_data = parseHex(param);
        }
        i2c_write_register(current_address, current_reg, current_data);
        break;

      case 's':
        scanBus();
        break;

      case 'h':
        printMenu();
        break;

      default:
        Serial.println("Unknown - type 'h' for help");
        break;
    }
  }
}