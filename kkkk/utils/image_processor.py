from PIL import Image
import os


class ImageProcessor:
    def init(self, image_path):
        self.image = Image.open(image_path)
        self.path = image_path

    def resize(self, width=None, height=None):
        """Resize image while maintaining aspect ratio"""
        original_width, original_height = self.image.size

        if width and height:
            new_size = (width, height)
        elif width:
            ratio = width / original_width
            new_size = (width, int(original_height * ratio))
        elif height:
            ratio = height / original_height
            new_size = (int(original_width * ratio), height)
        else:
            return self

        self.image = self.image.resize(new_size, Image.Resampling.LANCZOS)
        return self

    def convert(self, format='JPEG', quality=85):
        """Convert image to specified format"""
        if format.upper() == 'JPG':
            format = 'JPEG'
        self.format = format
        self.quality = quality
        return self

    def save(self, output_path):
        """Save processed image"""
        if self.image.mode == 'RGBA' and self.format == 'JPEG':
            # JPEG doesn't support transparency, convert to RGB
            rgb_image = Image.new('RGB', self.image.size, (255, 255, 255))
            rgb_image.paste(self.image, mask=self.image.split()[3] if self.image.mode == 'RGBA' else None)
            rgb_image.save(output_path, self.format, quality=self.quality, optimize=True)
        else:
            self.image.save(output_path, self.format, quality=self.quality, optimize=True)

    def get_info(self):
        """Get image information"""
        return {
            'format': self.image.format,
            'size': self.image.size,
            'mode': self.image.mode,
            'file_size': os.path.getsize(self.path)
        }