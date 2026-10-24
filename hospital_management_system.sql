CREATE DATABASE IF NOT EXISTS hospital_management_system;
USE hospital_management_system;

CREATE TABLE IF NOT EXISTS departments (
    department_id INT AUTO_INCREMENT PRIMARY KEY,
    department_name VARCHAR(100) NOT NULL,
    location VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS doctors (
    doctor_id INT AUTO_INCREMENT PRIMARY KEY,
    department_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    specialization VARCHAR(100),
    phone VARCHAR(20),
    email VARCHAR(255) UNIQUE,
    CONSTRAINT fk_doctors_department
        FOREIGN KEY (department_id) REFERENCES departments(department_id)
);

CREATE TABLE IF NOT EXISTS patients (
    patient_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    dob DATE,
    phone VARCHAR(20),
    address VARCHAR(255),
    blood_group VARCHAR(10)
);

CREATE TABLE IF NOT EXISTS rooms (
    room_id INT AUTO_INCREMENT PRIMARY KEY,
    room_type VARCHAR(50),
    ward VARCHAR(50),
    bed_number VARCHAR(20),
    status VARCHAR(30)
);

CREATE TABLE IF NOT EXISTS appointments (
    app_id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT NOT NULL,
    doctor_id INT NOT NULL,
    date DATE NOT NULL,
    time TIME NOT NULL,
    status VARCHAR(30),
    reason VARCHAR(255),
    CONSTRAINT fk_appointments_patient
        FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    CONSTRAINT fk_appointments_doctor
        FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id)
);

CREATE TABLE IF NOT EXISTS visits (
    visit_id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT NOT NULL,
    visit_date DATE NOT NULL,
    diagnosis VARCHAR(255),
    notes TEXT,
    treatment VARCHAR(255),
    CONSTRAINT fk_visits_patient
        FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);

CREATE TABLE IF NOT EXISTS bills (
    bill_id INT AUTO_INCREMENT PRIMARY KEY,
    visit_id INT NOT NULL UNIQUE,
    amount DECIMAL(10, 2) NOT NULL,
    date DATE NOT NULL,
    status VARCHAR(30),
    payment_mode VARCHAR(30),
    CONSTRAINT fk_bills_visit
        FOREIGN KEY (visit_id) REFERENCES visits(visit_id)
);

CREATE TABLE IF NOT EXISTS medicines (
    medicine_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    dosage VARCHAR(100),
    price DECIMAL(10, 2),
    stock INT
);

CREATE TABLE IF NOT EXISTS medical_records (
    record_id INT AUTO_INCREMENT PRIMARY KEY,
    visit_id INT NOT NULL,
    medicine_id INT,
    room_id INT,
    details TEXT,
    prescription TEXT,
    test_results TEXT,
    CONSTRAINT fk_medical_records_visit
        FOREIGN KEY (visit_id) REFERENCES visits(visit_id),
    CONSTRAINT fk_medical_records_medicine
        FOREIGN KEY (medicine_id) REFERENCES medicines(medicine_id),
    CONSTRAINT fk_medical_records_room
        FOREIGN KEY (room_id) REFERENCES rooms(room_id)
);

CREATE TABLE IF NOT EXISTS lab_tests (
    test_id INT AUTO_INCREMENT PRIMARY KEY,
    test_name VARCHAR(100) NOT NULL,
    cost DECIMAL(10, 2),
    result VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS medical_record_lab_tests (
    record_test_id INT AUTO_INCREMENT PRIMARY KEY,
    record_id INT NOT NULL,
    test_id INT NOT NULL,
    CONSTRAINT uq_record_lab_test UNIQUE (record_id, test_id),
    CONSTRAINT fk_record_lab_tests_record
        FOREIGN KEY (record_id) REFERENCES medical_records(record_id),
    CONSTRAINT fk_record_lab_tests_test
        FOREIGN KEY (test_id) REFERENCES lab_tests(test_id)
);

CREATE TABLE IF NOT EXISTS app_users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
