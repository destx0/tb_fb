import cv2
import numpy as np
import os


def hex_to_bgr(hex_color):
    hex_color = hex_color.lstrip("#")
    rgb = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return rgb[::-1]


def remove_specific_color(input_path, target_color, tolerance=30):
    img = cv2.imread(input_path)

    if img is None:
        print(f"Error: Could not read the image at {input_path}")
        return None

    target_color = hex_to_bgr(target_color)

    lower_bound = np.array([max(0, c - tolerance) for c in target_color])
    upper_bound = np.array([min(255, c + tolerance) for c in target_color])
    mask = cv2.inRange(img, lower_bound, upper_bound)

    mask = cv2.bitwise_not(mask)
    result = cv2.bitwise_and(img, img, mask=mask)
    result[mask == 0] = 255

    return result


def increase_contrast(image, alpha=1.5, beta=0):
    return cv2.convertScaleAbs(image, alpha=alpha, beta=beta)


def make_greys_darker(image, gamma=0.7):
    invGamma = 1.0 / gamma
    table = np.array(
        [((i / 255.0) ** invGamma) * 255 for i in np.arange(0, 256)]
    ).astype("uint8")
    return cv2.LUT(image, table)


def process_image(input_path, output_path, target_color, contrast_alpha=1.5, gamma=0.2):
    # Remove watermark
    result = remove_specific_color(input_path, target_color)
    if result is None:
        return

    # Increase contrast
    result = increase_contrast(result, alpha=contrast_alpha)

    # Convert to grayscale
    result = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)

    # Make greys darker
    result = make_greys_darker(result, gamma=gamma)

    # Ensure the output path has a supported extension
    file_name, file_extension = os.path.splitext(output_path)
    if file_extension.lower() not in [".png", ".jpg", ".jpeg"]:
        output_path = file_name + ".png"

    # Save the final result
    success = cv2.imwrite(output_path, result)
    if success:
        print(f"Processed image saved to {output_path}")
    else:
        print(f"Error: Failed to save the processed image to {output_path}")

    return output_path  # Return the actual path used for saving
