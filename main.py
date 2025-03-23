import requests
from bs4 import BeautifulSoup
import os
import threading
import time
from PIL import Image, UnidentifiedImageError

def download_image(image_url, save_directory, index):
    """Tải và lưu một ảnh từ URL và kiểm tra xem có phải ảnh hợp lệ không, kèm theo index."""
    filepath = None
    filepath_temp = None # Initialize filepath_temp outside try block
    try:
        image_response = requests.get(image_url, stream=True, timeout=10)
        image_response.raise_for_status()

        filename_base, ext = os.path.splitext(os.path.basename(image_url))
        filepath_temp = os.path.join(save_directory, filename_base + ext)

        with open(filepath_temp, 'wb') as file:
            for chunk in image_response.iter_content(chunk_size=8192):
                file.write(chunk)

        try:
            img = Image.open(filepath_temp)
            img.verify()

            # Convert to JPG if not already JPG
            if img.format != 'JPEG':
                img = img.convert('RGB') # Ensure RGB for JPEG
                filepath = os.path.join(save_directory, filename_base + ".jpg")
                img.save(filepath, 'JPEG') # Save as JPG
                os.remove(filepath_temp) # Remove the original file
                filename = os.path.basename(filepath) # Update filename
                print(f"Thread {threading.current_thread().name}: Đã tải, chuyển đổi và lưu (index {index}): {filename}")

            else: # Already JPEG, just rename to .jpg if needed (though unlikely)
                filepath = os.path.join(save_directory, filename_base + ".jpg")
                if filepath != filepath_temp: # Rename only if extension was different
                    os.rename(filepath_temp, filepath)
                else:
                    filepath = filepath_temp # Keep original path if no rename needed

                filename = os.path.basename(filepath)
                print(f"Thread {threading.current_thread().name}: Đã tải và lưu (index {index}): {filename}")

            img.close()
            return filepath, index  # Trả về filepath và index

        except UnidentifiedImageError:
            if filepath_temp and os.path.exists(filepath_temp):
                os.remove(filepath_temp)
            print(f"Thread {threading.current_thread().name}: Lỗi: File không phải là ảnh hợp lệ (index {index}): {os.path.basename(image_url)} từ {image_url}")
            return None, index  # Trả về None và index
        except Exception as e_verify:
            if filepath_temp and os.path.exists(filepath_temp):
                os.remove(filepath_temp)
            print(f"Thread {threading.current_thread().name}: Lỗi xác minh ảnh (index {index}) {os.path.basename(image_url)} từ {image_url}: {e_verify}")
            return None, index  # Trả về None và index

    except requests.exceptions.RequestException as e_request:
        print(f"Thread {threading.current_thread().name}: Lỗi khi tải ảnh từ (index {index}) {image_url}: {e_request}")
        return None, index  # Trả về None và index
    except Exception as e_overall:
        print(f"Thread {threading.current_thread().name}: Lỗi không xác định khi tải ảnh từ (index {index}) {image_url}: {e_overall}")
        return None, index  # Trả về None và index
    finally:
        if filepath_temp and filepath is None and os.path.exists(filepath_temp):
            os.remove(filepath_temp)


def clear_image_directory(directory):
    """Deletes all files in the specified directory (used to clear 'images' folder before new download)."""
    deleted_count = 0
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        try:
            if os.path.isfile(file_path):  # Only delete files, not subdirectories (if any somehow exist)
                os.remove(file_path)
                deleted_count += 1
        except Exception as e:
            print(f"Lỗi khi xóa {file_path}: {e}")
    print(f"Đã xóa {deleted_count} file cũ trong thư mục ảnh.")


def download_images_from_url(url, save_directory="images", num_threads=5):
    """
    Cào dữ liệu từ URL, tìm các thẻ img trong div có class 'item-photo',
    tải và lưu ảnh về thư mục chỉ định, sử dụng đa luồng và đảm bảo thứ tự.
    Xóa thư mục ảnh trước khi tải ảnh mới.

    Args:
        url (str): URL của trang web cần cào dữ liệu.
        save_directory (str): Thư mục để lưu ảnh (mặc định là 'images').
        num_threads (int): Số lượng thread đồng thời sử dụng (mặc định là 5).
    Returns:
        list: List of downloaded image filepaths in original order, or None if download fails
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    full_save_directory = os.path.join(script_dir, save_directory)

    if os.path.exists(full_save_directory):
        clear_image_directory(full_save_directory) # Clear directory before download
    else:
        os.makedirs(full_save_directory)

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        item_photo_divs = soup.find_all('div', class_='item-photo')

        image_urls = []
        for div in item_photo_divs:
            img_tag = div.find('img')
            if img_tag and 'src' in img_tag.attrs:
                image_urls.append(img_tag['src'])

        downloaded_files_with_index = [None] * len(image_urls) # Danh sách chứa kết quả tải, giữ chỗ theo index
        threads = []
        for index, image_url in enumerate(image_urls): # Duyệt qua image_urls kèm index
            thread = threading.Thread(target=download_and_store, args=(image_url, full_save_directory, index, downloaded_files_with_index)) # Truyền index và danh sách kết quả
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        downloaded_files_ordered = []
        for filepath, index in downloaded_files_with_index: # Lặp qua kết quả theo thứ tự index
            if filepath: # Chỉ lấy filepath nếu tải thành công
                filepath_full = os.path.join(full_save_directory, os.path.basename(filepath)) # Lấy đường dẫn đầy đủ
                if os.path.isfile(filepath_full) and filepath_full.lower().endswith(('.jpg')): # Check only for .jpg as we convert to jpg
                    try:
                        Image.open(filepath_full).verify()
                        downloaded_files_ordered.append(filepath_full)
                    except UnidentifiedImageError:
                        print(f"Warning: Found potentially invalid image file after download: {os.path.basename(filepath_full)}, skipping from merge.")
                        os.remove(filepath_full)

        print("Hoàn thành tải ảnh.")
        return downloaded_files_ordered # Trả về danh sách filepath đã sắp xếp theo thứ tự

    except requests.exceptions.RequestException as e:
        print(f"Lỗi khi truy cập URL {url}: {e}")
        return None
    except Exception as e_overall_download_func:
        print(f"Lỗi không xác định trong hàm download_images_from_url: {e_overall_download_func}")
        return None

def download_and_store(image_url, save_directory, index, results_list):
    """Hàm trung gian để tải ảnh và lưu kết quả vào danh sách ở vị trí index."""
    filepath, original_index = download_image(image_url, save_directory, index)
    results_list[original_index] = (filepath, original_index) # Lưu kết quả vào đúng vị trí index


def get_unique_filename(output_directory, filename_base):
    """
    Generates a unique filename by appending a counter if the base filename already exists.
    Improved to handle sequential indexing based on existing files.
    """
    counter = 1
    while True:
        output_filename = f"{filename_base}_{counter}.jpg"
        output_filepath = os.path.join(output_directory, output_filename)
        if not os.path.exists(output_filepath):
            return output_filepath
        counter += 1


def merge_images(image_files, output_name_prefix="merged_image", output_directory="."):
    """Merges images vertically and saves them to the specified output directory, splitting into parts if necessary, handling filename collisions."""
    if not image_files:
        print("Không có file ảnh hợp lệ để ghép!")
        return None

    images = []
    valid_image_files = []
    for img_path in image_files:
        try:
            img = Image.open(img_path)
            images.append(img)
            valid_image_files.append(img_path)
        except UnidentifiedImageError:
            print(f"Warning: Skipping invalid image file during merge: {img_path}")
            continue

    if not images:
        print("Không có file ảnh hợp lệ để ghép sau khi kiểm tra!")
        return None

    max_width = max(img.width for img in images)
    MAX_HEIGHT = 65000
    current_height = 0
    current_images = []
    part = 1
    merged_filenames = []

    for img in images:
        if current_height + img.height > MAX_HEIGHT and current_images:
            merged = Image.new("RGB", (max_width, current_height), (255, 255, 255))
            y_offset = 0
            for im in current_images:
                merged.paste(im, (0, y_offset))
                y_offset += im.height
            output_filename_base = f"{output_name_prefix}"

            # Improved filename generation - no part in base name anymore
            output_filename = get_unique_filename(output_directory, output_filename_base)
            merged.save(output_filename, 'JPEG') # Save as JPEG
            merged_filenames.append(output_filename)
            print(f"Đã lưu phần {part}: {output_filename}")

            part += 1
            current_height = img.height
            current_images = [img]
        else:
            current_height += img.height
            current_images.append(img)

    if current_images:
        merged = Image.new("RGB", (max_width, current_height), (255, 255, 255))
        y_offset = 0
        for im in current_images:
            merged.paste(im, (0, y_offset))
            y_offset += im.height
        output_filename_base = f"{output_name_prefix}"
        output_filename = get_unique_filename(output_directory, output_filename_base) # Get unique filename
        merged.save(output_filename, 'JPEG') # Save as JPEG
        merged_filenames.append(output_filename)
        print(f"Đã lưu phần {part}: {output_filename}")

    print("Ảnh đã được ghép thành công!")
    return merged_filenames, valid_image_files


def delete_images_in_directory(directory, valid_image_files=None):
    """Deletes image files in the directory, keeping merged parts if valid_image_files is provided."""
    deleted_count = 0
    if valid_image_files is None:
        for filename in os.listdir(directory):
            if filename.lower().endswith(('.jpg')): # Only delete jpg as we convert to jpg
                file_path = os.path.join(directory, filename)
                try:
                    os.remove(file_path)
                    print(f"Đã xóa: {file_path}")
                    deleted_count += 1
                except Exception as e:
                    print(f"Lỗi khi xóa {file_path}: {e}")
    else:
        valid_filenames = {os.path.basename(f) for f in valid_image_files}
        for filename in os.listdir(directory):
             if filename.lower().endswith(('.jpg')) and filename not in valid_filenames: # Only check for jpg
                file_path = os.path.join(directory, filename)
                try:
                    os.remove(file_path)
                    print(f"Đã xóa: {file_path}")
                    deleted_count += 1
                except Exception as e:
                    print(f"Lỗi khi xóa {file_path}: {e}")

    print(f"Đã xóa {deleted_count} ảnh gốc.")


if __name__ == "__main__":
    url_trang_web = input("Nhập URL trang web bạn muốn cào ảnh: ")
    num_threads_input = input("Nhập số lượng thread đồng thời (mặc định là 5): ")
    num_threads = int(num_threads_input) if num_threads_input else 5
    merged_image_name = input("Nhập tên cho ảnh ghép (ví dụ: ThienSuNhaBen): ")
    if not merged_image_name:
        merged_image_name = "merged_image"

    output_directory_input = input("Nhập đường dẫn thư mục lưu ảnh ghép (để trống để lưu cùng thư mục script): ")
    output_directory = output_directory_input.strip()
    if not output_directory:
        output_directory = "."  # Current directory as default
    elif not os.path.isdir(output_directory): # Basic validation: check if path exists and is a directory
        print(f"Cảnh báo: Đường dẫn '{output_directory}' không hợp lệ hoặc không tồn tại. Lưu ảnh ghép vào thư mục script.")
        output_directory = "."


    start_time = time.time()
    downloaded_image_files = download_images_from_url(url_trang_web, num_threads=num_threads)
    end_time = time.time()
    total_download_time = end_time - start_time
    print(f"Tổng thời gian tải: {total_download_time:.2f} giây")

    if downloaded_image_files:
        print("\nBắt đầu ghép ảnh...")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        save_directory = os.path.join(script_dir, "images")
        downloaded_image_paths = downloaded_image_files # Danh sách đã được sắp xếp rồi

        merge_start_time = time.time()
        merge_result = merge_images(downloaded_image_paths, output_name_prefix=merged_image_name, output_directory=output_directory) # Pass output_directory
        merge_end_time = time.time()
        total_merge_time = merge_end_time - merge_start_time
        print(f"Tổng thời gian ghép ảnh: {total_merge_time:.2f} giây")

        if merge_result:
            merged_files, valid_original_files = merge_result
            delete_images_in_directory(save_directory, valid_original_files)
            print(f"\nCác file ảnh ghép đã được lưu vào thư mục '{output_directory}' với tên bắt đầu bằng '{merged_image_name}'.")
        else:
            print("\nGhép ảnh không thành công do không có ảnh hợp lệ hoặc lỗi trong quá trình ghép.")

    else:
        print("Không có ảnh nào được tải về thành công, không thể ghép ảnh.")