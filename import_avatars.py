import os
import csv
from django.core.files import File
from sms.models import Student, StudentSession, EduSession

# ==========================================
# CONFIGURATION
# ==========================================
# Replace these with your actual absolute paths
CSV_FILE_PATH = r"/import/samata_itahari_2083.csv"
IMAGES_FOLDER_PATH = r"/import/images/samata_itahari_2083"
TARGET_SESSION_YEAR = "2083"
# ==========================================

def run_import():
    print("Starting avatar import process...")
    
    if not os.path.exists(CSV_FILE_PATH):
        print(f"ERROR: CSV file not found at {CSV_FILE_PATH}")
        return

    if not os.path.exists(IMAGES_FOLDER_PATH):
        print(f"ERROR: Images folder not found at {IMAGES_FOLDER_PATH}")
        return

    try:
        current_session = EduSession.objects.get(session_year=TARGET_SESSION_YEAR)
    except EduSession.DoesNotExist:
        print(f"ERROR: Session year '{TARGET_SESSION_YEAR}' not found in database.")
        return

    # 1. Read CSV into a dictionary: { reg_no: photo_name }
    avatar_mapping = {}
    with open(CSV_FILE_PATH, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            reg_no = row.get("Reg.")
            photo_name = row.get("PhotoName")
            if reg_no and photo_name:
                avatar_mapping[str(reg_no).strip()] = str(photo_name).strip()
    
    print(f"Loaded {len(avatar_mapping)} mappings from CSV.")

    # 2. Get students in the current session
    student_sessions = StudentSession.objects.filter(session=current_session, status=True).select_related('student')
    print(f"Found {student_sessions.count()} active student sessions for {TARGET_SESSION_YEAR}.")

    success_count = 0
    not_found_count = 0
    missing_image_count = 0

    for ss in student_sessions:
        student = ss.student
        reg_no = str(student.reg_no)

        # Check if this student's reg_no is in the CSV
        if reg_no in avatar_mapping:
            photo_name = avatar_mapping[reg_no]
            photo_path = os.path.join(IMAGES_FOLDER_PATH, photo_name)

            if os.path.exists(photo_path):
                # Open the image file and attach to Django FileField
                with open(photo_path, 'rb') as f:
                    django_file = File(f, name=photo_name)
                    
                    # 1. Save to core Student profile (this automatically copies to the new dynamic path)
                    student.avatar.save(photo_name, django_file, save=True)
                    
                    # Reset the file pointer back to the beginning before saving again
                    f.seek(0)
                    
                    # 2. Save to StudentSession
                    ss.avatar.save(photo_name, django_file, save=True)
                
                success_count += 1
                print(f"[{success_count}] Success: Uploaded avatar for Reg. {reg_no}")
            else:
                missing_image_count += 1
                print(f"WARNING: Image '{photo_name}' not found in folder for Reg. {reg_no}")
        else:
            not_found_count += 1

    print("\n--- IMPORT SUMMARY ---")
    print(f"Successfully imported: {success_count}")
    print(f"Images missing from folder: {missing_image_count}")
    print(f"Students missing from CSV: {not_found_count}")

if __name__ == "__main__":
    run_import()
