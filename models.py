from extensions import db


class Room(db.Model):
    __tablename__ = 'room'
    room_id = db.Column(db.String(), primary_key=True)
    username = db.Column(db.String(), primary_key=True)
    language = db.Column(db.String(), primary_key=True)
    language_level = db.Column(db.Integer(), primary_key=True)

    def __repr__(self):
        return f'<Room "{self.room_id}"'

    @classmethod
    def find_suitable_room(cls, language, language_level):
        if language == 'kaz':
            need_language = 'eng'
        else:
            need_language = 'kaz'

        room = cls.query.filter_by(language=need_language, language_level=language_level).first()
        room.delete()
        return room
    def save(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()