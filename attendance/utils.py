import cv2
import numpy as np
from .models import Profile

def find_matching_face(image_to_check):
    """
    Takes an image file, compares it against all known faces, and returns the best match.
    """
    # 1. Prepare training data from all users
    profiles = Profile.objects.filter(reference_image__isnull=False).exclude(reference_image='')
    if not profiles.exists():
        return None, None, "No registered faces in the system."

    faces = []
    labels = []
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    for profile in profiles:
        if hasattr(profile.reference_image, 'path'):
            image_path = profile.reference_image.path
            ref_img = cv2.imread(image_path)
            if ref_img is None:
                continue # Skip corrupted or missing images
            gray_ref_img = cv2.cvtColor(ref_img, cv2.COLOR_BGR2GRAY)
            detected_faces = face_cascade.detectMultiScale(gray_ref_img, 1.1, 5)
            if len(detected_faces) > 0:
                (x, y, w, h) = detected_faces[0]
                faces.append(gray_ref_img[y:y+h, x:x+w])
                labels.append(profile.user.id)

    if not faces:
        return None, None, "Could not extract any faces from reference images."

    # 2. Train the recognizer
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(faces, np.array(labels))

    # 3. Process the image to check
    image_to_check.seek(0)
    img_data = image_to_check.read()
    np_arr = np.frombuffer(img_data, np.uint8)
    img_to_check_cv = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    gray_img_to_check = cv2.cvtColor(img_to_check_cv, cv2.COLOR_BGR2GRAY)

    detected_faces_uploaded = face_cascade.detectMultiScale(gray_img_to_check, 1.1, 5)
    if len(detected_faces_uploaded) == 0:
        return None, None, "No face detected in the provided image."

    # 4. Make a prediction
    (x, y, w, h) = detected_faces_uploaded[0]
    predicted_label, confidence = recognizer.predict(gray_img_to_check[y:y+h, x:x+w])

    # 5. Return the result
    CONFIDENCE_THRESHOLD = 80
    if confidence < CONFIDENCE_THRESHOLD:
        return predicted_label, confidence, "Match found."
    else:
        return None, confidence, "No confident match found."


def verify_user_face(user, image_to_verify):
    try:
        profile = user.profile
        if not profile.reference_image or not hasattr(profile.reference_image, 'path'):
            return False, "No reference image for user."
    except Profile.DoesNotExist:
        return False, "No profile for user."

    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    # 1. "Train" on the user's reference image
    image_path = profile.reference_image.path
    ref_img = cv2.imread(image_path)
    if ref_img is None:
        return False, "Could not read reference image file."
    gray_ref_img = cv2.cvtColor(ref_img, cv2.COLOR_BGR2GRAY)

    ref_faces = face_cascade.detectMultiScale(gray_ref_img, 1.1, 5)
    if len(ref_faces) == 0:
        return False, "Could not find face in reference image."

    (x, y, w, h) = ref_faces[0]
    face_to_train = gray_ref_img[y:y+h, x:x+w]

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train([face_to_train], np.array([user.id]))

    # 2. Predict on the new image
    image_to_verify.seek(0)
    uploaded_img_data = image_to_verify.read()
    np_arr = np.frombuffer(uploaded_img_data, np.uint8)
    uploaded_img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    gray_uploaded_img = cv2.cvtColor(uploaded_img, cv2.COLOR_BGR2GRAY)

    uploaded_faces = face_cascade.detectMultiScale(gray_uploaded_img, 1.1, 5)
    if len(uploaded_faces) == 0:
        return False, "No face detected in provided image."

    (x, y, w, h) = uploaded_faces[0]
    label, confidence = recognizer.predict(gray_uploaded_img[y:y+h, x:x+w])

    # 3. Check confidence
    CONFIDENCE_THRESHOLD = 85
    if label == user.id and confidence < CONFIDENCE_THRESHOLD:
        return True, "Face verified."
    else:
        return False, f"Face does not match. Confidence: {confidence}"
