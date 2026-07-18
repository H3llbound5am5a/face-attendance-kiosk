#!/bin/bash
# Face Attendance Kiosk - Dependency Installer for Pi 5 (Bookworm)

echo "[1/4] Updating System Repositories..."
sudo apt update && sudo apt upgrade -y

echo "[2/4] Installing System-Level Build Dependencies..."
# Needed to compile dlib (face_recognition) and for OpenCV
sudo apt install -y libopencv-dev libatlas-base-dev libhdf5-dev cmake gfortran libopenblas-dev liblapack-dev

echo "[3/4] Creating Python Virtual Environment..."
python3 -m venv --clear biometric_env

echo "[4/4] Installing Python Libraries..."
source biometric_env/bin/activate

# Upgrade pip first
pip install --upgrade pip

# Core Math & Vision
pip install numpy opencv-python-headless mediapipe

# Face Recognition (This takes 15-20 mins to compile on Pi!)
echo " - Installing face-recognition (Get a coffee, this takes time)..."
pip install face_recognition

# UI
pip install pygame

echo "-----------------------------------------------"
echo "SETUP COMPLETE!"
echo "To start working, type: source biometric_env/bin/activate"
echo "To run the kiosk:       python main.py"
echo "-----------------------------------------------"
