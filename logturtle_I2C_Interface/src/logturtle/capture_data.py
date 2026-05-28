import ctypes
from dwfconstants import *
import sys
import time
import csv
import numpy as np
import matplotlib.pyplot as plt

# --- DWF Library Loading ---
if sys.platform.startswith("win"):
    dwf = ctypes.cdll.dwf
elif sys.platform.startswith("darwin"):
    dwf = ctypes.cdll.LoadLibrary("/Library/Frameworks/dwf.framework/dwf")
else:
    dwf = ctypes.cdll.LoadLibrary("libdwf.so")

# --- CUSTOM PROTOCOL CONFIGURATION Constants ---
TIME_TO_FIRST_PULSE_NS = 1170
DELAYS_NS = [400, 430, 460, 460, 470, 480, 475, 480, 510, 510, 475] # 11 transitions for 12 bits

def save_raw_signals_to_csv(raw_samples, sample_period_ns, filename="raw_signals_capture.csv"):
    print(f"Exporting raw signals to {filename}...")
    try:
        with open(filename, mode='w', newline='') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(["Time_ns", "DIO0_Data", "DIO1_Comp", "DIO2_Clock"])
            
            for idx, sample in enumerate(raw_samples):
                current_time_ns = idx * sample_period_ns
                bit0 = (sample >> 0) & 1  # DIO 0
                bit1 = (sample >> 1) & 1  # DIO 1
                bit2 = (sample >> 2) & 1  # DIO 2
                
                writer.writerow([f"{current_time_ns:.2f}", bit0, bit1, bit2])
        print("Raw signals CSV export complete.")
    except Exception as e:
        print(f"Error saving raw CSV: {e}")

def capture_data(duration_sec=1.0, SR=100000000.0, plot=False, save=False, csv_filename="deserialized_data.csv", save_raw=True, raw_filename="raw_signals_capture.csv"):
    """
    Captures digital data streams from Digital Discovery, validates frames using XOR (DIO6 ^ DIO7),
    and extracts DIO6 words into decimal format.
    
    :param duration_sec: Capture duration in seconds
    :param SR: Targeted Sampling Rate in Hz (e.g., 24000000)
    :param plot: If True, plots the final decoded decimal values
    :param save: If True, saves decoded data to a CSV file
    :param csv_filename: Name of the output CSV file
    :param save_raw: If True, saves raw signals to a CSV file
    :param raw_filename: Name of the raw signals CSV file
    """
    hdwf = ctypes.c_int()
    sts = ctypes.c_ubyte()
    hzDI = ctypes.c_double()
    
    print("Opening Digital Discovery...")
    dwf.FDwfDeviceOpen(ctypes.c_int(-1), ctypes.byref(hdwf))
    if hdwf.value == 0:
        print("Error: Failed to open device.")
        return

    # Disable auto-configuration to allow manual batch configuration
    dwf.FDwfDeviceAutoConfigureSet(hdwf, ctypes.c_int(0))
    
    # Query base internal clock frequency
    dwf.FDwfDigitalInInternalClockInfo(hdwf, ctypes.byref(hzDI))
    
    # Calculate the clock divider needed to match requested Sampling Rate (SR)
    divSample = int(round(hzDI.value / SR))
    actual_SR = hzDI.value / divSample
    sample_period_ns = 1e9 / actual_SR
    
    # Calculate total digital samples to collect
    total_samples_to_record = int(duration_sec * actual_SR)
    
    print(f"-> Base Internal Frequency: {hzDI.value / 1e6:.2f} MHz")
    print(f"-> Configured Divider: {divSample} (Actual SR: {actual_SR / 1e6:.2f} MHz)")
    print(f"-> Sample Period: {sample_period_ns:.2f} ns")
    print(f"-> Target Samples to Collect: {total_samples_to_record}")

    # --- Hardware Interface Configuration ---
    dwf.FDwfDigitalInAcquisitionModeSet(hdwf, acqmodeRecord)
    dwf.FDwfDigitalInDividerSet(hdwf, ctypes.c_int(divSample))
    dwf.FDwfDigitalInSampleFormatSet(hdwf, ctypes.c_int(8))  # 8-bit format (DIN0 to DIN7)
    dwf.FDwfDigitalInTriggerPositionSet(hdwf, ctypes.c_int(0))
    dwf.FDwfDigitalInTriggerSourceSet(hdwf, trigsrcNone)
    dwf.FDwfDigitalInInputOrderSet(hdwf, ctypes.c_int(0))

    # Start recording stream
    dwf.FDwfDigitalInConfigure(hdwf, ctypes.c_int(0), ctypes.c_int(1))
    print("Recording stream active...")

    raw_samples = []
    samples_collected = 0
    
    cAvailable = ctypes.c_int()
    cLost = ctypes.c_int()
    cCorrupted = ctypes.c_int()
    
    # --- Data Streaming Acquisition Loop ---
    try:
        while samples_collected < total_samples_to_record:
            if dwf.FDwfDigitalInStatus(hdwf, ctypes.c_int(1), ctypes.byref(sts)) == 0:
                print("Hardware Status Error.")
                break
                
            dwf.FDwfDigitalInStatusRecord(hdwf, ctypes.byref(cAvailable), ctypes.byref(cLost), ctypes.byref(cCorrupted))
            
            if cLost.value > 0:
                print(f"\n USB Buffer Overflow! Lost {cLost.value} samples. Lower your SR parameter.")
            
            if cAvailable.value > 0:
                # Avoid reading past our targeted sample size boundary
                chunk_size = min(cAvailable.value, total_samples_to_record - samples_collected)
                rgbBuffer = (ctypes.c_uint8 * chunk_size)()
                
                dwf.FDwfDigitalInStatusData(hdwf, ctypes.byref(rgbBuffer), ctypes.c_int(chunk_size))
                
                # Append raw binary block chunk to memory list
                raw_samples.extend(rgbBuffer)
                samples_collected += chunk_size
                print(f"Streaming data: {samples_collected}/{total_samples_to_record} samples captured...", end="\r")
                
    finally:
        # Disconnect hardware session cleanly
        dwf.FDwfDeviceClose(hdwf)
        print("\nHardware acquisition closed completed.")
    
    if save_raw and raw_samples:
        save_raw_signals_to_csv(raw_samples, sample_period_ns, filename=raw_filename)

    # # --- Custom Protocol Processing Phase ---
    # print("Processing digital signals and parsing frames...")
    # decoded_values = []
    # pClock = 0
    # total_len = len(raw_samples)
    
    # for i in range(total_len):
    #     sample = raw_samples[i]
    #     clockState = (sample >> 2) & 1  # DIO 2
        
    #     # Detect Rising Edge on DIO 4
    #     if clockState == 1 and pClock == 0:
    #         word_dio6 = 0
    #         is_frame_valid = True
    #         current_offset_ns = TIME_TO_FIRST_PULSE_NS
            
    #         for bitIdx in range(12):
    #             if bitIdx > 0:
    #                 current_offset_ns += DELAYS_NS[bitIdx - 1]
                
    #             # Turn absolute elapsed time offset into strict indexing reference
    #             target_index = i + int(round(current_offset_ns / sample_period_ns))
                
    #             if target_index < total_len:
    #                 target_sample = raw_samples[target_index]
    #                 bit6 = (target_sample >> 0) & 1  # DIO 0 Data
    #                 bit7 = (target_sample >> 1) & 1  # DIO 1 Complement
                    
    #                 # Protocol Verification Step (XOR Check)
    #                 if (bit6 ^ bit7) != 1:
    #                     is_frame_valid = False
    #                     break
                    
    #                 # Shift bit into local reconstructed value variable (MSB first)
    #                 word_dio6 = (word_dio6 << 1) | bit6
    #             else:
    #                 is_frame_valid = False
    #                 break
            
    #         # If the differential check passes completely, commit the value
    #         if is_frame_valid:
    #             decoded_values.append(word_dio6)
                
    #     pClock = clockState

    # print(f"Parsing done! Found {len(decoded_values)} valid 12-bit frames.")

    # # --- CSV File Export Generation ---
    # if save and decoded_values:
    #     print(f"Exporting results to {csv_filename}...")
    #     with open(csv_filename, mode='w', newline='') as csv_file:
    #         writer = csv.writer(csv_file)
    #         # Layout matching requested structure:
    #         # Column 1 = Decimal values, Column 2 = Serial index count
    #         writer.writerow(["DIO6_Value_Decimal", "Index"])
    #         for idx, val in enumerate(decoded_values):
    #             writer.writerow([val, idx])
    #     print("CSV export complete.")

    # # --- Graphical Waveform Rendering ---
    # if plot and decoded_values:
    #     if len(decoded_values) == 0:
    #         print("No valid decoded data available to generate plot layout.")
    #         return
    #     plt.figure(figsize=(10, 5))
    #     plt.step(range(len(decoded_values)), decoded_values, where='mid', color='b', label='DIO6 Value')
    #     plt.title('Decoded Parallel Bus Data Over Time (Decimal)')
    #     plt.xlabel('Frame Serial Index')
    #     plt.ylabel('Value (12-bit Decimal Integer)')
    #     plt.grid(True, linestyle='--')
    #     plt.legend()
    #     plt.show()


    # return decoded_values


# --- Execution Entry Point ---
if __name__ == "__main__":
    # Example execution configuration:
    # Captures for 0.025 seconds at a targeted 100MHz sampling frequency rate
    data = capture_data(
        duration_sec=0.025, 
        SR=50000000.0, 
        plot=True, 
        save=True, 
        csv_filename="deserialized_data.csv",
        save_raw=True,
        raw_filename="raw_signals_capture.csv"
    )
    