import serial
import serial.tools.list_ports
import time
import sys
import webbrowser
import os
from collections import Counter

session_history = []
history_index = -1

BAUD_RATE = 115200

GITHUB_EXCEL_URL = "https://github.com/AmrT26/logturtle_I2C_Testing/blob/main/Reg%20Map.xlsx"

# ANSI Escape Codes for console text coloring
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_RESET = "\033[0m"

teensy = None
verbose_mode = False

# Global dictionaries to track register modifications and current states
history_registers = {}
VALID_REGISTERS = list(range(0, 8)) + list(range(16, 29))

DEFAULT_REG_VALUES = {
    0: 0b00000000,
    1: 0b10010000,
    2: 0b10100000,
    3: 0b00010100,
    4: 0b00100000,
    5: 0b00100000,
    6: 0b00000000,
    7: 0b00110000,
    # not needed for now
    16: 0b00100000,
    17: 0b00010000,
    18: 0b11111111,
    19: 0b00000000,
    20: 0b00011011,
    21: 0b00000000,
    22: 0b00000000,
    23: 0b01001100,
    24: 0b00100000,
    25: 0b00000000,
    26: 0b00000100,
    27: 0b00000000,
    28: 0b00000000
}

current_reg_states = DEFAULT_REG_VALUES.copy()


def smart_input(prompt):
    global session_history, history_index
    try:
        user_input = input(prompt).strip()

        if user_input.lower() == 'z':
            if session_history:
                history_index -= 1
                if history_index < -len(session_history):
                    history_index = -1

                chosen_command = session_history[history_index]
                print(f"[Recall] -> {chosen_command}")
                return chosen_command
            else:
                print("[!] No history available.")
                return ""

        if user_input:
            if not session_history or session_history[-1] != user_input:
                session_history.append(user_input)
            history_index = 0

        return user_input

    except KeyboardInterrupt:
        print("\n[!] Interrupted.")
        return ""
    except EOFError:
        return ""


def find_teensy_port():
    print("[INFO] Automatic detection of the Teensy...")
    ports = list(serial.tools.list_ports.comports())  # Retrieve all active COM ports on the computer

    # First : Look specifically for a device identifying as "Teensy"
    for p in ports:
        description = str(p.description).lower()
        manufacturer = str(p.manufacturer).lower() if p.manufacturer else ""

        if "teensy" in description or "teensy" in manufacturer:
            print(f"[OK] Teensy detected on port: {p.device} ({p.description})")
            return p.device

    # Fallback menu to manually pick a port if automatic detection fails
    if ports:
        print(f"[WARNING] No device explicitly named 'Teensy' found.")
        print(f"[INFO] Multiple COM ports are active. Please select the correct one:")

        for index, p in enumerate(ports):
            print(f"  [{index}] -> {p.device} ({p.description})")

        while True:
            try:
                choice = smart_input("Enter the number of your Teensy port: ").strip()
                choice_idx = int(choice)
                if 0 <= choice_idx < len(ports):
                    selected_port = ports[choice_idx].device
                    print(f"[INFO] Using selected port: {selected_port}")
                    return selected_port
                else:
                    print(f"[!] Invalid selection. Choose between 0 and {len(ports) - 1}")
            except ValueError:
                print("[!] Please enter a valid number.")

    print("[ERROR] No active COM ports detected. Is the Teensy plugged in?")
    return None


def parse_any_base(user_input):
    val_str = str(user_input).strip().lower().replace(" ",
                                                      "")  # Removes internal spaces to accept formats such as '0010 0001'

    try:
        if val_str.startswith("0b"):
            val = int(val_str, 2)
        elif val_str.startswith("0x"):
            val = int(val_str, 16)
        elif len(val_str) == 8 and all(c in '01' for c in val_str):
            val = int(val_str, 2)
        elif any(c in 'abcdef' for c in val_str):
            val = int(val_str, 16)
        else:
            val = int(val_str, 10)

        if val < 0 or val > 255:
            raise ValueError("The value exceed 8 bits (0-255).")

        return f"0x{val:02x}"

    except ValueError as e:
        print(f"[!] Interpretation error of '{user_input}': {e}")
        return None


def get_universal_input(prompt_message, default_value=None):
    while True:
        user_input = smart_input(prompt_message).strip()
        if not user_input and default_value is not None:
            return parse_any_base(default_value)
        if not user_input:
            print("[!] Empty input. Try again.")
            continue
        parsed = parse_any_base(user_input)
        if parsed is not None:
            return parsed


def format_binary_with_colors(current_val, default_val):
    bin_current = f"{current_val:08b}"
    bin_default = f"{default_val:08b}"

    formatted_chars = []
    for i in range(8):
        if i == 4:
            formatted_chars.append(" ")

        if bin_current[i] != bin_default[i]:
            formatted_chars.append(f"{COLOR_RED}{bin_current[i]}{COLOR_RESET}")
        else:
            formatted_chars.append(bin_current[i])

    return "".join(formatted_chars)


def process_teensy_output(device, is_read_operation=False, silent=False):
    time.sleep(0.02)
    lines = []

    while device.in_waiting > 0:
        line = device.readline().decode('utf-8', errors='ignore').strip()
        if line:
            if "[i2c write]" in line.lower() or "[i2c read]" in line.lower():
                continue
            lines.append(line)
            if verbose_mode:
                print(f"  {line}")

    if not verbose_mode:
        output_str = " ".join(lines).lower()

        if "nack" in output_str or "failed" in output_str:
            if not silent:
                print(f"  -> {COLOR_RED}NACK / FAIL{COLOR_RESET}")
            return None

        if is_read_operation and "data:" in output_str:
            parts = output_str.split("data:")
            if len(parts) > 1:
                after_data = parts[1].replace(",", " ").replace(";", " ").replace(":", " ").split()
                for word in after_data:
                    if word.startswith("0x"):
                        try:
                            val_int = int(word, 16)
                            if not silent:
                                print(
                                    f"  -> {COLOR_GREEN}ACK{COLOR_RESET} | Data read: 0x{val_int:02x} ({val_int:08b})")
                            return f"0x{val_int:02x}"
                        except ValueError:
                            pass
            if not silent:
                print(f"  -> {COLOR_GREEN}ACK{COLOR_RESET} | Success (No data extracted)")
            return "0x00"

        else:
            if not silent:
                print(f"  -> {COLOR_GREEN}ACK{COLOR_RESET} | Success")
            return "0x00"

    return "0x00"


def i2c_write(reg, data, max_retries=3, retry_delay=0.05):
    global teensy
    # Automatic conversion of inputs to the format required by the Teensy (‘0xXX’)
    hex_addr = "0x20"
    hex_reg = parse_any_base(reg)
    hex_data = parse_any_base(data)

    if not (hex_reg and hex_data):
        print("[!] Write operation failed: invalid parameters.")
        return False

    print(f"\n[I2C WRITE] Chip: {hex_addr} | Reg: {hex_reg} | Data: {hex_data}")

    for attempt in range(1, max_retries + 1):

        teensy.write(f"a {hex_addr}\n".encode('utf-8'))
        time.sleep(0.02)

        teensy.write(f"i {hex_reg}\n".encode('utf-8'))
        time.sleep(0.02)

        teensy.write(f"w {hex_data}\n".encode('utf-8'))

        old_verbose = verbose_mode
        globals()['verbose_mode'] = False

        result = process_teensy_output(teensy, is_read_operation=False, silent=True)

        globals()['verbose_mode'] = old_verbose

        if result is not None:  # ACK received
            reg_int = int(hex_reg, 16)
            data_int = int(hex_data, 16)

            if reg_int in VALID_REGISTERS:
                current_reg_states[reg_int] = data_int
                history_registers[reg_int] = (hex_reg, hex_data)
            if attempt == 1:
                print(f"  -> {COLOR_GREEN}ACK{COLOR_RESET} | Success")
            else:
                print(f"  -> {COLOR_GREEN}ACK{COLOR_RESET} | Success [{attempt}/{max_retries} attempts]")
            return True

        time.sleep(retry_delay)

    print(f"{COLOR_RED}[FAIL] No ACK after {max_retries} attempts.{COLOR_RESET}")
    return False


def i2c_read(reg, silent=False, max_retries=5, retry_delay=0.05):
    global teensy, current_reg_states
    hex_addr = "0x20"
    hex_reg = parse_any_base(reg)

    if not (hex_reg):
        print("[!] Read operation failed: invalid parameters.")
        return

    if verbose_mode:
        print(f"\n[I2C READ] Chip: {hex_addr} | Reg: {hex_reg}")

    results = []

    for attempt in range(1, max_retries + 1):
        teensy.write(f"a {hex_addr}\n".encode('utf-8'))
        time.sleep(0.02)
        teensy.write(f"r {hex_reg}\n".encode('utf-8'))

        old_verbose = verbose_mode
        globals()['verbose_mode'] = False

        res = process_teensy_output(teensy, is_read_operation=True, silent=True)

        globals()['verbose_mode'] = old_verbose

        if res is not None:
            results.append(res)

        time.sleep(retry_delay)
    if not results:
        if not silent:
            print(f"  {COLOR_RED}[FAIL] No ACK after {max_retries} attempts.{COLOR_RESET}")
        return None

    counter = Counter(results)
    winner, count = counter.most_common(1)[0]

    if not silent:
        val_int = int(winner, 16)
        print(f"-> {COLOR_GREEN}ACK{COLOR_RESET} "
              f"| Data: {winner} "
              f"({val_int:08b}) "
              f"[{count}/{max_retries} reads]")
    reg_int = int(hex_reg, 16)
    if reg_int in VALID_REGISTERS:
        current_reg_states[reg_int] = int(winner, 16)
    return winner


def show_write_history():
    print("\n" + "=" * 50)
    print("   HISTORY OF MODIFIED REGISTERS")
    print("=" * 50)

    if not history_registers:
        print("  [Pending] No entries have been made yet.")
        print("=" * 50)
        return

    print(f" {'Register':<12} | {'Last Data Written (Hexa)':<30}")
    print("-" * 50)

    sorted_registers = sorted(history_registers.keys())

    for reg_int in sorted_registers:
        hex_reg, hex_data = history_registers[reg_int]
        data_int = int(hex_data, 16)
        bin_data = f"0b{data_int:08b}"

        print(f"  {hex_reg:<10} | {hex_data}  ({bin_data})")

    print("=" * 50)


def read_and_display_all_map(chip_addr="0x20"):
    global verbose_mode, current_reg_states

    print("\n" + "=" * 40)
    print(f" REGISTER MAP - CHIP {chip_addr}")
    print(" (Red bits = modified vs default)")
    print("=" * 40)

    for reg in VALID_REGISTERS:
        reg_label = f"  Reg {reg:<2} (0x{reg:02x})"

        res = i2c_read(hex(reg), silent=True)

        if res and res.startswith("0x"):
            # Update state
            reg_int = int(hex(reg), 16)
            current_reg_states[reg_int] = int(res, 16)

            # Format with colors
            current_val = current_reg_states[reg]
            default_val = DEFAULT_REG_VALUES[reg]
            binary_str = format_binary_with_colors(
                current_val, default_val)
            data_str = f"{binary_str} ({res})"

        else:
            data_str = f"{COLOR_RED}NACK / FAIL{COLOR_RESET}"

        print(f"{reg_label} : {data_str}")

    print("=" * 40)


def clear_history_and_states():
    global history_registers, current_reg_states
    history_registers.clear()
    current_reg_states = DEFAULT_REG_VALUES.copy()
    print(f"\n[OK] History cleared. All registers reset to their default values.")


def execute_test_file(test_number):
    prefix = f"test_{test_number}_"
    filename = None

    try:
        for file_in_dir in os.listdir("."):
            if file_in_dir.lower().startswith(prefix) and file_in_dir.lower().endswith(".txt"):
                filename = file_in_dir
                break
    except Exception as e:
        print(f"[ERROR] Impossible de scanner le dossier : {e}")
        return

    if not filename:
        print(f"\n[ERROR] Aucun fichier trouvé commençant par '{prefix}' et finissant par '.txt'.")
        print("Vérifie que ton fichier est bien présent dans le répertoire courant.")
        return

    print("\n" + "=" * 50)
    print(f" AUTOMATIC TEST EXECUTION : {filename}")
    print("=" * 50)

    try:
        with open(filename, "r", encoding='utf-8') as file:
            lines = file.readlines()

        for line_num, line in enumerate(lines, 1):
            clean_line = line.strip()

            if not clean_line or clean_line.startswith("#"):
                continue

            if "," not in clean_line:
                print(f"[WARNING] Line {line_num} ignored (incorrectly formatted) : '{clean_line}'")
                continue

            reg_part, data_part = clean_line.split(",", 1)

            write_success = i2c_write(reg_part.strip(), data_part.strip())
            if write_success:
                time.sleep(0.05)
                i2c_read(reg_part.strip())
                time.sleep(0.05)

    except Exception as e:
        print(f"[ERROR] An error occurred whilst reading the file : {e}")

    print("\n" + "=" * 50)
    print(f" END TEST EXECUTION : {filename}")
    print("=" * 50)


def test_anatest():
    print("\n" + "=" * 50)
    print(" Anatest setup")
    print("=" * 50)
    print("\n--- Reg 0: enable all encluding irefvref_En : ---")

    i2c_write(0x20, 0, 0xFF)
    time.sleep(0.1)
    i2c_read(0x20, 0)  # verification

    print("\n--- Reg 0: enable vcm buf and adc adcvref buffs : ---")

    i2c_write(1, "10010011")
    time.sleep(0.1)
    i2c_read(0)  # verification

    print("\n--- Reg 24  - Enable BGap  : ---")

    i2c_write(24, "00100001")
    time.sleep(0.1)
    i2c_read(24)  # verification

    print("\n--- Reg 3  - AnaTest Bus out cfg : ---")

    i2c_write(3, "11010100")  # XXX 1 0100
    time.sleep(0.1)
    i2c_read(3)  # verification

    print("\n" + "=" * 50)
    print(" END OF AUTOMATIC TEST")
    print("=" * 50)

def test_adctest():
    print("\n" + "=" * 50)
    print(" ADC Test Setup")
    print("=" * 50)
    
    # i2c_adc_en	i2c_pga2_en	i2c_lna2_en	i2c_adcbufn_en	i2c_adcbufp_en	i2c_pga1_en	i2c_lna1_en	i2c_irefvref_en
    # 1	            0	        0	        1	            1	            0	        0	        1

    i2c_write(0, "10011001")
    time.sleep(0.1)
    i2c_read(0)  # verification

    # dig_PGA2_gain_ctrl[2]	dig_PGA2_gain_ctrl[1]	dig_PGA2_gain_ctrl[0]	dig_PGA1_gain_ctrl[2]	dig_PGA1_gain_ctrl[1]	dig_PGA1_gain_ctrl[0]	i2c_vcmbuf_en	i2c_adcvrefbufs_en
    # 0	                    0	                    0	                    0	                    0	                    0	                    1	            1

    i2c_write(1, "00000011")
    time.sleep(0.1)
    i2c_read(1)  # verification

    # dig_ADC_Cbalast_code_P[4]	dig_ADC_Cbalast_code_P[3]	dig_ADC_Cbalast_code_P[2]	dig_ADC_Cbalast_code_P[1]	dig_ADC_Cbalast_code_P[0]	i2c_adc_rstb	dig_ADC_mode_sel[1]	dig_ADC_mode_sel[0]
    # 1	                        0	                        1	                        0	                        0	                        0	            1	                0
    # set ADC mode, and pull rstb high
    i2c_write(2, "10100110")
    time.sleep(0.1)
    i2c_read(2)  # verification

    # set ADC mode, and pull rstb low
    i2c_write(2, "10100010")
    time.sleep(0.1)
    i2c_read(2)  # verification

    # — —   —	—	i2c_sel_adc_vcm_mux_ips	dig_en_ADC_comp_outputs	dig_ADC_Buf_swap_override	dig_ADC_Buf_swap_override_en
    # 0 0	  0	0	0	                    1	                    0	                        0

    i2c_write(6, "00000100")
    time.sleep(0.1)
    i2c_read(6)  # verification

    # —	—	ADC_CLKSelect_25kHz	ADC_CLKSelect_51kHz	ADC_CLKSelect_102kHz	dig_ChoppingCLK_Select_102kHz	dig_EN_Bypass_DLL_Filter	dig_EN_Bypass_PLL_Filter
    # 0	0	0	                1	                0	                    0	                            0	                        0
    
    i2c_write(17, "00001000")
    time.sleep(0.1)
    i2c_read(17)  # verification

    print("\n" + "=" * 50)
    print(" END OF ADC SETUP")
    print("=" * 50)


def connect_to_teensy():
    actual_port = find_teensy_port()
    if not actual_port:
        print("[ERROR] Connection impossible : No COM port has been detected.")
    try:
        print(f"[INFO] Connection to Teensy on {actual_port}...")
        device = serial.Serial(actual_port, BAUD_RATE, timeout=1)
        time.sleep(2)
        print("[OK] Connected !\n")
        return device
    except serial.SerialException as e:
        print(f"[ERROR] Impossible to connect to the port {actual_port}.")
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
        user_input = smart_input(prompt_message).strip().lower()
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
    print("  [m] -> Show this MENU")
    print("  [z] -> Type 'z' + Enter to recall PREVIOUS command")
    print("  [g] -> Last input")
    print("  [s] -> Scaning the I2C bus")
    print("  [v] -> Toggle VERBOSE mode")
    print("  [r] -> READ a register")
    print("  [w] -> WRITE in a register")
    print("  [a] -> Set analog test mux (anatest)")
    print("  [o] -> OPEN Excel Register Map (GitHub)")
    print("  [rm]-> READ and DUMP the REGISTER MAP on the chip")
    print("  [t] -> LAUNCH test file(ex: 't' or 't 1', 't 2')")
    print("  [oldt] -> LAUNCH test_anatest()")
    print("  [h] -> View the HISTORY of written registers")
    print("  [ch]-> CLEAR HISTORY")
    print("  [q] -> Quit the application")
    print("-" * 40)


def execute_anatest_menu():
    global teensy
    print("\n" + "=" * 40)
    print(" PRINT OUT ANALOG TEST MENU")
    print("=" * 40)
    print("  0 : Off")
    print("  1 : irefP -> insert R10")
    print("  2 : irefN -> insert R9")
    print("  3 : Clk Gen iTest -> insert R11")
    print("  4 : ADC_VCM")
    print("  5 : ADC_VrefP")
    print("  6 : ADC_VrefN")
    print("  7 : Vbandgap Buffered")
    print("-" * 40)

    while True:
        choice_input = smart_input("Please enter your anaTest choice (0-7) : ").strip()
        if not choice_input:
            print("[!] Empty input. Operation cancelled.")
            return
        try:
            choice = int(choice_input)
            if 0 <= choice <= 7:
                break
            print("[!] Invalid choice. Must be between 0 and 7.")
        except ValueError:
            print("[!] Please enter a valid number.")

    print(f"\n[INFO] Reading current state of Register 3...")

    current_reg3_hex = i2c_read("3", silent=True)

    if not current_reg3_hex:
        print(f"{COLOR_RED}[ERROR] Could not read Register 3. Operation aborted.{COLOR_RESET}")
        return

    current_val = int(current_reg3_hex, 16)

    lower_5_bits = current_val & 0x1F

    upper_3_bits = (choice & 0x07) << 5

    new_reg3_value = upper_3_bits | lower_5_bits

    print(f"  Current value : 0x{current_val:02x} ({current_val:08b})")
    print(f"  New value     : 0x{new_reg3_value:02x} ({new_reg3_value:08b})")

    write_success = i2c_write("3", hex(new_reg3_value))

    if write_success:
        print(f"\n{COLOR_GREEN}[OK] Analog Test Mux successfully updated to setting {choice}!{COLOR_RESET}")
        time.sleep(0.02)
        i2c_read("3")
    else:
        print(f"\n{COLOR_RED}[ERROR] Failed to update Register 3.{COLOR_RESET}")


def main():
    global teensy, verbose_mode
    teensy = connect_to_teensy()
    read_all_from_teensy(teensy)

    last_action = {
        "choice": None,
        "reg": None,
        "data": None
    }

    print_user_menu()

    while True:
        raw_input = smart_input("\nChoose an action (type 'm' for menu) : ").strip()
        if not raw_input:
            continue

        parts = raw_input.split()
        choice = parts[0].lower()

        if choice == 'm':
            print_user_menu()
            continue

        if choice == 'g':
            if last_action["choice"] is None:
                print("\n[!] No action has been performed yet during this session.")
                continue

            prev_choice = last_action["choice"]

            if prev_choice == 'r':
                print(f"\n[REPEAT] Quick READ -> Chip: Reg: {last_action['reg']}")
                i2c_read(last_action["reg"])
                continue

            elif prev_choice == 'w':
                print(
                    f"\n[REPEAT] Quick WRITE -> Chip: Reg: {last_action['reg']} | Data: {last_action['data']}")
                i2c_write(last_action["reg"], last_action["data"])
                continue

            else:
                print(f"\n[REPEAT] Re-executing action... (Choice: [{prev_choice}])")
                choice = prev_choice

        if choice in ['s', 'v', 'r', 'w', 'o', 'rm', 't', 'h', 'ch']:
            if choice not in ['r', 'w', 'rm']:
                last_action["choice"] = choice

        if choice == 's':
            print("\n[Action] Complete Scan of the I2C bus...")
            teensy.write(b's\n')
            read_all_from_teensy(teensy)

        elif choice == 'v':
            verbose_mode = not verbose_mode
            print(f"\n[INFO] Verbose mode toggled. Now it is {'ON' if verbose_mode else 'OFF'}.")

        elif choice == 'r':
            print("\n--- READING CONFIGURATION ---")
            print("(Accepted formats : Hexa '0x40', Binaire '0b0010', Décimal '64')")
            reg = get_universal_input("2. Register number (ex: 0x02) : ")
            last_action = {"choice": 'r', "reg": reg, "data": None}
            i2c_read(reg)

        elif choice == 'w':
            print("\n--- WRITING CONFIGURATION ---")
            print("(Accepted formats : Hexa '0x20', Binaire '0b0010', Décimal '64')")
            reg = get_universal_input("2. Register number (ex: 0x00) : ")
            data = get_universal_input("3. Data value (ex: 0xAB) : ")
            last_action = {"choice": 'w', "reg": reg, "data": data}
            i2c_write(reg, data)

        elif choice == 'a':
            execute_anatest_menu()
            last_action = {"choice": 'a', "reg": None, "data": None}

        elif choice == 'o':
            open_excel_on_github()

        elif choice == 'rm':
            read_and_display_all_map("0x20")
            last_action = {"choice": 'rm', "reg": None, "data": None}

        elif choice == 't':
            if len(parts) > 1:
                test_num = parts[1]
            else:
                test_num = smart_input("Enter test number : ").strip()

            if test_num:
                last_action = {"choice": 't', "addr": "0x20", "reg": test_num, "data": None}
                execute_test_file(test_num)
            else:
                print("[!] Invalid test number.")

        elif choice == 'oldt':
            test_anatest()

        elif choice == 'h':
            show_write_history()

        elif choice == 'ch':
            clear_history_and_states()

        elif choice == 'q':
            print("\nClosing the interface. Session ended.")
            teensy.close()
            break
        else:
            print("\n[!] invalid Option. Select 1, 2, 3, 4 ou Q.")


if __name__ == "__main__":
    main()