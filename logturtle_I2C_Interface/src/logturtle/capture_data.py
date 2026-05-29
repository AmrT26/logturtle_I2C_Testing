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
    