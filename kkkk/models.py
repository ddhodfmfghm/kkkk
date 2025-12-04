from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class ImageConversion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_filename = db.Column(db.String(200), nullable=False)
    converted_filename = db.Column(db.String(200), nullable=False)
    original_format = db.Column(db.String(10), nullable=False)
    converted_format = db.Column(db.String(10), nullable=False)
    original_size = db.Column(db.Integer, nullable=False)  # in bytes
    converted_size = db.Column(db.Integer, nullable=False)  # in bytes
    quality = db.Column(db.Integer, default=85)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_size_reduction(self):
        if self.original_size > 0:
            reduction = ((self.original_size - self.converted_size) / self.original_size) * 100
            return round(reduction, 2)
        return 0


def init_app(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()