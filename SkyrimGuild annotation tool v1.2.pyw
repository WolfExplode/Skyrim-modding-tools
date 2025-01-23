import os
import re
import json
import subprocess
import shutil
import traceback
import tkinter
from tkinter.filedialog import askopenfilename, askdirectory
from tkinter.simpledialog import askstring
import tkinter.messagebox
import concurrent.futures

def show_error(message, exception=None):
    error_msg = f"{message}\n\nError details: {str(exception)}" if exception else message
    tkinter.messagebox.showerror("Error", error_msg)
    if exception:
        with open("annotation_tool_error.log", "a") as log_file:
            log_file.write(f"{message}\n")
            traceback.print_exc(file=log_file)

def is_float(value):
    try:
        float(value)
        return True
    except ValueError:
        return False

def update_files(filename, fileAnnotations):
    try:
        txt_path = f"{hkannoDirectory}{filename[:-3]}txt"
        with open(txt_path, 'w') as file:
            for line in fileAnnotations:
                file.write(f"{line}\n")
        
        result = subprocess.run(
            [jsonContent["HKanno"], "update", "-i", f"{filename[:-3]}txt", 
             f"{filename}", f"{filename}"],
            cwd=hkannoDirectory,
            shell=True,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise Exception(f"HKanno update failed:\n{result.stderr}")
            
        src_hkx = f"{hkannoDirectory}{filename}"
        dest_folder = jsonContent["Animations Folder"]
        
        for path in [src_hkx, txt_path]:
            if not os.path.exists(path):
                raise FileNotFoundError(f"File not found: {path}")
            
            dest = os.path.join(dest_folder, os.path.basename(path))
            shutil.move(path, dest)
            
    except Exception as e:
        show_error(f"Failed to update files for {filename}", e)
        raise

def select_directory(json_folder, error_message):
    noAnimFoundFlag = False
    while True:
        try:
            if json_folder not in jsonContent.keys() or not os.path.isdir(jsonContent[json_folder]):
                raise ValueError("Invalid directory path")
                
            anim_list = get_animations_list(jsonContent[json_folder])
            if len(anim_list) == 0:
                raise ValueError("No animations found")
                
            return jsonContent[json_folder]
            
        except Exception as e:
            if noAnimFoundFlag:
                show_error(error_message, e)
            noAnimFoundFlag = True
            new_path = askdirectory()
            if not new_path:
                quit()
            jsonContent[json_folder] = new_path

def get_values_from_json_key(json_key):
    return jsonContent.get(json_key, [])

def get_animations_list(folder):
    try:
        return [f for f in os.listdir(folder) if f.lower().endswith('.hkx')]
    except Exception as e:
        show_error(f"Error listing animations in {folder}", e)
        return []

def move_files_to_hkanno_folder(animationFile):
    try:
        src_hkx = f'{jsonContent["Animations Folder"]}\\{animationFile}'
        dest_hkx = f"{hkannoDirectory}{animationFile}"
        
        if not os.path.exists(src_hkx):
            raise FileNotFoundError(f"Source file not found: {src_hkx}")
            
        shutil.move(src_hkx, dest_hkx)
        
        txt_file = f'{jsonContent["Animations Folder"]}\\{animationFile[:-3]}txt'
        if os.path.isfile(txt_file):
            shutil.move(txt_file, f"{hkannoDirectory}{animationFile[:-3]}txt")
        else:
            animationToDump.append(animationFile)
            
    except Exception as e:
        show_error(f"Failed moving files for {animationFile}", e)
        raise

def process_annotations(animationFile):
    try:
        txt_path = f"{hkannoDirectory}{animationFile[:-3]}txt"
        if not os.path.exists(txt_path):
            raise FileNotFoundError(f"Annotation file missing: {txt_path}")

        with open(txt_path, 'r') as file:
            fileAnnotationsBuffer = [line.rstrip() for line in file if len(line.rstrip()) >= 2]

        # Existing processing logic for Remove
        for annotationToRemove in get_values_from_json_key("Remove"):
            fileAnnotationsBuffer = [line for line in fileAnnotationsBuffer if annotationToRemove not in line]

        # Existing processing logic for Add
        for annotationToAdd in get_values_from_json_key("Add"):
            if len(annotationToAdd.split()) >= 2 and is_float(annotationToAdd.split()[0]):
                fileAnnotationsBuffer.append(annotationToAdd)
                continue

            timing = askstring(f'Time missing for {annotationToAdd}', 
                f"You need to input the time to add the '{annotationToAdd}' annotation.\nCurrent annotations for {animationFile}\n: {chr(10).join([line for line in fileAnnotationsBuffer if 'animmotion' not in line and 'animrotation' not in line])}")
            if not timing:
                continue

            if not is_float(timing):
                raise ValueError(f"Invalid timing value: {timing}")

            fileAnnotationsBuffer.append(f"{timing} {annotationToAdd}")

        # New: Handle SpeedMultiplier
        speed_multiplier = jsonContent.get("SpeedMultiplier")
        if speed_multiplier is not None:
            speed_time = jsonContent.get("SpeedTime")
            found = False
            for i, line in enumerate(fileAnnotationsBuffer):
                if "PIE.@SGVF|MCO_AttackSpeed|" in line:
                    parts = line.strip().split()
                    if len(parts) < 2:
                        continue
                    time_part, annotation = parts[0], parts[1]
                    annotation_parts = annotation.split('|')
                    if len(annotation_parts) < 3:
                        continue
                    try:
                        current_value = float(annotation_parts[2])
                    except ValueError:
                        continue
                    new_value = round(current_value * speed_multiplier, 2)
                    annotation_parts[2] = f"{new_value:.2f}"
                    new_line = f"{time_part} {'|'.join(annotation_parts)}"
                    fileAnnotationsBuffer[i] = new_line
                    found = True
            if not found:
                if speed_time is not None:
                    base_value = 1.0  # Adjust if a different base is needed
                    new_value = round(base_value * speed_multiplier, 2)
                    new_line = f"{speed_time:.6f} PIE.@SGVF|MCO_AttackSpeed|{new_value:.2f}"
                    fileAnnotationsBuffer.append(new_line)
                else:
                    show_error(f"SpeedTime missing in JSON for {animationFile}")

        # Existing replacement logic (updated)
        for oldAnnotation, newAnnotation in jsonContent.items():
            if str(oldAnnotation) not in ["HKanno", "Animations Folder", "Extracted Motion", "Remove", "Add"]:
                fileAnnotationsBuffer = [
                    line.replace(str(oldAnnotation), str(newAnnotation))  # Convert both to strings
                    for line in fileAnnotationsBuffer
                ]

        update_files(animationFile, fileAnnotationsBuffer)

    except Exception as e:
        show_error(f"Failed processing annotations for {animationFile}", e)
        raise


# Main execution
try:
    overwriteJsonFlag = False
    jsonContent = {}

    # Load JSON with error handling
    jsonPresetFilename = "Anno_Fast.json" if os.path.isfile("Anno_Fast.json") else askopenfilename(filetypes=[("Annotations", "*.json")])
    if not jsonPresetFilename:
        quit()

    try:
        with open(jsonPresetFilename, 'r') as jsonPresetFile:
            jsonContent = json.load(jsonPresetFile)
    except json.JSONDecodeError as e:
        show_error(f"Invalid JSON format in {jsonPresetFilename}", e)
        quit()
    except Exception as e:
        show_error(f"Error loading JSON file", e)
        quit()

    # HKanno path validation
    if os.path.isfile("hkanno64.exe"):
        jsonContent["HKanno"] = "hkanno64.exe"
        
    while "HKanno" not in jsonContent or not os.path.isfile(jsonContent["HKanno"]):
        jsonContent["HKanno"] = askopenfilename(filetypes=[("HKanno64", "*.exe")])
        overwriteJsonFlag = True
        if not jsonContent["HKanno"]:
            quit()

    hkannoDirectory = f'{os.path.dirname(jsonContent["HKanno"])}\\'
    
    if overwriteJsonFlag:
        try:
            with open(jsonPresetFilename, 'w') as jsonPresetFile:
                json.dump(jsonContent, jsonPresetFile, indent=2)
        except Exception as e:
            show_error("Failed to save updated JSON config", e)

    try:
        jsonContent["Animations Folder"] = os.getcwd() if len(get_animations_list(os.getcwd())) > 0 else select_directory("Animations Folder", "No animation found in selected directory")
    except Exception as e:
        show_error("Failed to set animations folder", e)
        quit()

    try:
        animationList = get_animations_list(jsonContent["Animations Folder"])
    except Exception as e:
        show_error("Failed to get animation list", e)
        quit()

    animationToDump = []

    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.map(move_files_to_hkanno_folder, animationList)
    except Exception as e:
        show_error("Error during file transfer to HKanno directory", e)
        quit()

    try:
        for animationFile in animationToDump:
            result = subprocess.run(
                [jsonContent["HKanno"], "dump", "-o", f"{animationFile[:-3]}txt", f"{animationFile}"],
                cwd=hkannoDirectory,
                shell=True,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                raise Exception(f"HKanno dump failed for {animationFile}:\n{result.stderr}")
    except Exception as e:
        show_error("Error during HKanno dump operation", e)
        quit()

    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.map(process_annotations, animationList)
    except Exception as e:
        show_error("Error during annotation processing", e)

except Exception as e:
    show_error("Critical error in main execution", e)