"""
图片处理模块 - 处理图片上传和安全验证
"""
import os
import hashlib
from PIL import Image
from io import BytesIO
from .config import BASE_DIR
import warnings

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024
TARGET_SIZE = (120, 120)

IMAGE_DIR = os.path.join(BASE_DIR, 'static', 'img')


def get_image_dir():
    """获取图片保存目录，确保存在"""
    os.makedirs(IMAGE_DIR, exist_ok=True)
    return IMAGE_DIR


def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_image_content(file_data):
    """
    验证图片内容是否安全，防止图片木马
    通过尝试打开图片来验证
    """
    try:
        img = Image.open(BytesIO(file_data))
        img.verify()
        return True
    except Exception:
        return False


def resize_and_save_image(file_data, filename):
    """
    处理并保存图片
    1. 验证图片内容
    2. 裁剪为120x120
    3. 保存到static/img目录
    """
    try:
        if not validate_image_content(file_data):
            return None, '无效的图片文件'
        
        if len(file_data) > MAX_FILE_SIZE:
            return None, f'图片文件过大，最大支持{MAX_FILE_SIZE // (1024*1024)}MB'
        
        img = Image.open(BytesIO(file_data))
        
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            
            if img.mode == 'P':
                if 'transparency' in img.info:
                    img = img.convert('RGBA').convert('RGB')
                else:
                    img = img.convert('RGB')
            elif img.mode == 'RGBA':
                img = img.convert('RGB')
            elif img.mode == 'L':
                img = img.convert('RGB')
        
        width, height = img.size
        min_dim = min(width, height)
        
        left = (width - min_dim) // 2
        top = (height - min_dim) // 2
        right = left + min_dim
        bottom = top + min_dim
        
        img = img.crop((left, top, right, bottom))
        img = img.resize(TARGET_SIZE, Image.Resampling.LANCZOS)
        
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'jpg'
        if ext not in ALLOWED_EXTENSIONS:
            ext = 'jpg'
        
        file_hash = hashlib.md5(file_data).hexdigest()[:16]
        safe_filename = f"{file_hash}.{ext}"
        
        save_path = os.path.join(get_image_dir(), safe_filename)
        img.save(save_path, 'JPEG', quality=85, optimize=True)
        
        return f"img/{safe_filename}", None
        
    except Exception as e:
        print(f"图片处理失败: {e}")
        return None, f'图片处理失败: {str(e)}'


def save_uploaded_file(file, custom_filename=None):
    """
    保存上传的文件并处理
    """
    try:
        if not file or not file.filename:
            return None, '没有上传文件'
        
        if not allowed_file(file.filename):
            return None, f'不支持的文件类型，只支持: {", ".join(ALLOWED_EXTENSIONS)}'
        
        file_data = file.read()
        
        if len(file_data) > MAX_FILE_SIZE:
            return None, f'文件过大，最大支持{MAX_FILE_SIZE // (1024*1024)}MB'
        
        if custom_filename:
            if '..' in custom_filename or '/' in custom_filename or '\\' in custom_filename:
                return None, '文件名包含非法字符'
            ext = custom_filename.rsplit('.', 1)[1].lower() if '.' in custom_filename else 'jpg'
            if ext not in ALLOWED_EXTENSIONS:
                ext = 'jpg'
            filename = f"{custom_filename}.{ext}"
        else:
            filename = file.filename
        
        result_path, error = resize_and_save_image(file_data, filename)
        if error:
            return None, error
        
        return result_path, None
        
    except Exception as e:
        print(f"文件保存失败: {e}")
        return None, f'文件保存失败: {str(e)}'


def delete_image(relative_path):
    """
    删除图片文件
    """
    try:
        if '..' in relative_path or not relative_path.startswith('img/'):
            return False
        
        full_path = os.path.join(BASE_DIR, 'static', relative_path)
        
        if os.path.exists(full_path):
            os.remove(full_path)
            return True
        return False
        
    except Exception as e:
        print(f"删除图片失败: {e}")
        return False


def get_image_url(relative_path):
    """
    获取图片的完整URL
    """
    if not relative_path:
        return ''
    
    if relative_path.startswith('http://') or relative_path.startswith('https://'):
        return relative_path
    
    return f"/static/{relative_path}"
