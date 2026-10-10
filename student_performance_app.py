from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import os
import re

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Stores uploaded Excel data while the app is running
exam_data = {}


# =========================================================
# FIND ROLL NUMBER COLUMN
# =========================================================

def find_roll_column(df):

    possible_names = [
        "roll",
        "roll number",
        "roll_number",
        "roll no",
        "roll_no",
        "rollno",
        "id",
        "student id",
        "student_id"
    ]

    for column in df.columns:

        clean = str(column).lower().strip()

        if clean in possible_names:
            return column

    # Partial matching
    for column in df.columns:

        clean = str(column).lower().strip()

        if "roll" in clean:
            return column

    return None


# =========================================================
# FIND STUDENT NAME COLUMN
# =========================================================

def find_name_column(df):

    possible_names = [
        "name",
        "student name",
        "student_name",
        "student"
    ]

    for column in df.columns:

        clean = str(column).lower().strip()

        if clean in possible_names:
            return column

    for column in df.columns:

        clean = str(column).lower().strip()

        if "name" in clean:
            return column

    return None


# =========================================================
# CLEAN MARK
# =========================================================

def clean_mark(value):

    if pd.isna(value):
        return "-"

    value = str(value).strip()

    if value == "":
        return "-"

    if value.lower() in ["absent", "ab", "a"]:
        return "Absent"

    try:

        number = float(value)

        if number.is_integer():
            return int(number)

        return round(number, 2)

    except:

        return value


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def home():

    uploaded_exams = list(exam_data.keys())

    return render_template(
        "index.html",
        uploaded_exams=uploaded_exams
    )


# =========================================================
# UPLOAD EXCEL FILES
# =========================================================

@app.route("/upload", methods=["POST"])
def upload():

    # Get every selected file from the form
    files = []

    for file in request.files.values():

        if file and file.filename:

            files.append(file)

    # Also support multiple="multiple" input
    extra_files = request.files.getlist("exam_files")

    for file in extra_files:

        if file and file.filename:

            if file not in files:
                files.append(file)

    # No files selected
    if not files:

        return "Please select at least one Excel file."

    # =====================================================
    # PROCESS EACH EXCEL FILE
    # =====================================================

    for file in files:

        filename = file.filename.strip()

        if not filename:
            continue

        # Check Excel format
        if not filename.lower().endswith((".xlsx", ".xls")):

            return (
                f"{filename} is not an Excel file. "
                "Please upload an Excel file."
            )

        # Safe filename
        safe_name = re.sub(
            r"[^a-zA-Z0-9_.-]",
            "_",
            filename
        )

        file_path = os.path.join(
            UPLOAD_FOLDER,
            safe_name
        )

        # Save Excel file
        file.save(file_path)

        # =================================================
        # READ EXCEL
        # =================================================

        try:

            df = pd.read_excel(file_path)

        except Exception as e:

            return f"Could not read {filename}: {e}"

        # Remove completely empty rows
        df = df.dropna(how="all")

        if df.empty:

            return f"{filename} is empty."

        # =================================================
        # FIND ROLL NUMBER
        # =================================================

        roll_column = find_roll_column(df)

        if roll_column is None:

            return (
                f"Roll number column not found in {filename}. "
                "Please use Roll Number, Roll No, or Roll."
            )

        # =================================================
        # FIND STUDENT NAME
        # =================================================

        name_column = find_name_column(df)

        # Normalize roll numbers
        df[roll_column] = (
            df[roll_column]
            .astype(str)
            .str.strip()
        )

        # Remove .0 from Excel roll numbers
        df[roll_column] = (
            df[roll_column]
            .str.replace(
                r"\.0$",
                "",
                regex=True
            )
        )

        # =================================================
        # STORE STUDENTS
        # =================================================

        students = {}

        for _, row in df.iterrows():

            roll = str(
                row[roll_column]
            ).strip()

            if not roll or roll.lower() == "nan":
                continue

            # Student name
            if name_column:

                student_name = str(
                    row[name_column]
                ).strip()

                if student_name.lower() == "nan":

                    student_name = "Student"

            else:

                student_name = "Student"

            # =================================================
            # AUTOMATIC SUBJECT DETECTION
            # =================================================

            subjects = {}

            for column in df.columns:

                # Ignore roll number
                if column == roll_column:
                    continue

                # Ignore student name
                if name_column and column == name_column:
                    continue

                subject_name = str(
                    column
                ).strip()

                if not subject_name:
                    continue

                mark = clean_mark(
                    row[column]
                )

                subjects[subject_name] = mark

            # Store student
            students[roll] = {

                "name": student_name,

                "roll": roll,

                "subjects": subjects
            }

        # =================================================
        # USE EXCEL FILE NAME AS ASSESSMENT NAME
        # =================================================

        exam_name = os.path.splitext(
            filename
        )[0]

        exam_data[exam_name] = students

    # Return to home page
    return redirect(
        url_for("home")
    )


# =========================================================
# SEARCH STUDENT
# =========================================================

@app.route("/student", methods=["POST"])
def student():

    roll_number = request.form.get(
        "roll_number",
        ""
    ).strip()

    if not roll_number:

        return "Please enter a roll number."

    # Remove .0 if entered
    roll_number = re.sub(
        r"\.0$",
        "",
        roll_number
    )

    # Stores this student's data
    # from every uploaded Excel file
    student_results = {}

    student_name = "Student"

    # =====================================================
    # SEARCH ALL UPLOADED EXCEL FILES
    # =====================================================

    for exam_name, students in exam_data.items():

        if roll_number in students:

            student_info = students[
                roll_number
            ]

            student_name = student_info[
                "name"
            ]

            student_results[
                exam_name
            ] = student_info[
                "subjects"
            ]

    # =====================================================
    # STUDENT NOT FOUND
    # =====================================================

    if not student_results:

        return render_template(
            "student.html",
            found=False,
            roll_number=roll_number
        )

    # =====================================================
    # FIND ALL SUBJECTS
    # =====================================================

    all_subjects = []

    for exam_name in student_results:

        subjects = student_results[
            exam_name
        ]

        for subject in subjects:

            if subject not in all_subjects:

                all_subjects.append(
                    subject
                )

    # =====================================================
    # SUBJECT PROGRESS
    # =====================================================

    subject_progress = {}

    for subject in all_subjects:

        values = []

        for exam_name in student_results:

            subjects = student_results[
                exam_name
            ]

            if subject in subjects:

                value = subjects[
                    subject
                ]

                try:

                    values.append(
                        float(value)
                    )

                except:

                    pass

        if values:

            subject_progress[
                subject
            ] = {

                "values": values,

                "average": round(
                    sum(values) /
                    len(values),
                    2
                )
            }

    # =====================================================
    # OVERALL AVERAGE
    # =====================================================

    overall_values = []

    for subject in subject_progress:

        average = subject_progress[
            subject
        ]["average"]

        overall_values.append(
            average
        )

    if overall_values:

        overall_average = round(
            sum(overall_values) /
            len(overall_values),
            2
        )

    else:

        overall_average = 0

    # =====================================================
    # SEND DATA TO STUDENT.HTML
    # =====================================================

    return render_template(

        "student.html",

        found=True,

        roll_number=roll_number,

        student_name=student_name,

        student_results=student_results,

        all_subjects=all_subjects,

        subject_progress=subject_progress,

        overall_average=overall_average
    )


# =========================================================
# RUN APP
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )