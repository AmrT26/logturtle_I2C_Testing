import serial
import time
import sys
import webbrowser

SERIAL_PORT = 'COM4'
BAUD_RATE = 115200

GITHUB_EXCEL_URL = "https://github.com/AmrT26/logturtle_I2C_Testing/blob/main/Reg%20Map.xlsx"

def connect_to_teensy():
    try:
        print(f"[INFO] Connection to Teensy on {SERIAL_PORT}...")
        device = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(2)
        print("[OK] Connected !\n")
        return device
    except serial.SerialException as e:
        print(f"[ERROR] Impossible to connect to the port {SERIAL_PORT}.")
        print(f"Détails : {e}")
        sys.exit(1)


def read_all_from_teensy(device):
    time.sleep(0.15)
    while device.in_waiting > 0:
        line = device.readline().decode('utf-8', errors='ignore').strip()
        if line:
            print(f"  {line}")


def get_hexa_input(prompt_message):
    while True:
        user_input = input(prompt_message).strip().lower()
        if not user_input:
            print("[!] Entrée vide. Recommence.")
            continue
        if not user_input.startswith("0x"):
            user_input = "0x" + user_input
        try:
            int(user_input, 16)
            return user_input
        except ValueError:
            print("[!] invalid value. expecting : 0x40, 0x02...")


def open_excel_on_github():
    print(f"[INFO] Opening the Excel Register Map on the browser...")
    webbrowser.open(GITHUB_EXCEL_URL)


def print_user_menu():
    print("\n" + "=" * 40)
    print("      I2C INTERFACE")
    print("=" * 40)
    print("  [1] -> Scaning the I2C bus")
    print("  [2] -> READ a register")
    print("  [3] -> WRITE in a register")
    print("  [4] -> OPEN the register map")
    print("  [Q] -> Quit the application")
    print("-" * 40)


def main():
    teensy = connect_to_teensy()
    read_all_from_teensy(teensy)

    while True:
        print_user_menu()
        choix = input("Choose an action : ").strip().lower()

        if choix == '1':
            print("\n[Action] Complete Scan of the I2C bus...")
            teensy.write(b's\n')
            read_all_from_teensy(teensy)

        elif choix == '2':
            print("\n--- READING CONFIGURATION ---")
            addr = get_hexa_input("1. Chip address (ex: 0x20) : ")
            reg = get_hexa_input("2. Register number (ex: 0x02) : ")

            teensy.write(f"a {addr}\n".encode('utf-8'))
            time.sleep(0.05)

            print(f"\n[Action] Reading of the register {reg} on the chip {addr}...")
            teensy.write(f"r {reg}\n".encode('utf-8'))
            read_all_from_teensy(teensy)

        elif choix == '3':
            print("\n--- WRITING CONFIGURATION ---")
            addr = get_hexa_input("1. Chip Address (ex: 0x20) : ")
            reg = get_hexa_input("2. Register number (ex: 0x00) : ")
            data = get_hexa_input("3. Data value (ex: 0xAB) : ")

            teensy.write(f"a {addr}\n".encode('utf-8'))
            time.sleep(0.05)
            teensy.write(f"i {reg}\n".encode('utf-8'))
            time.sleep(0.05)

            print(f"\n[Action] Writing of the data {data} in the register {reg} of the chip {addr}...")
            teensy.write(f"w {data}\n".encode('utf-8'))
            read_all_from_teensy(teensy)

        elif choix == '4':
            open_excel_on_github()

        elif choix == 'q':
            print("\nClosing the interface. Session ended.")
            teensy.close()
            break
        else:
            print("\n[!] invalid Option. Select 1, 2, 3, 4 ou Q.")


if __name__ == "__main__":
    main()