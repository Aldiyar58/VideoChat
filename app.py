from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

# Next two lines are for the issue: https://github.com/miguelgrinberg/python-engineio/issues/142
from engineio.payload import Payload
Payload.max_decode_packets = 200

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = "thisismys3cr3tk3yrree"
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://default:5lRaUgW1bLzo@ep-square-wind-a4xxqxcv-pooler.us-east-1.aws.neon.tech/verceldb?sslmode=require'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


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
        # filtered_rooms = list(filter(lambda ro: ro.language_level == language_level and ro.language == need_language, rooms))
        if room is not None:
            room.delete()
            return room
        return None

    def save(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        db.session.delete(self)
        db.session.commit()


socketio = SocketIO(app)

_users_in_room = {}  # stores room wise user list
_room_of_sid = {}  # stores room joined by a used
_name_of_sid = {}  # stores display name of users


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        room_id = request.form['room_id']
        return redirect(url_for("entry_checkpoint", room_id=room_id))
    return render_template("home.html")


@app.route("/find/companion/<string:username>/<string:language>/<int:language_level>/", methods=["GET", "POST"])
def find_companion(username, language, language_level):
    room = Room.find_suitable_room(language=language, language_level=language)  # todo: companion should be one level higher
    if room:
        return redirect(url_for(endpoint="enter_room", room_id=room.room_id))
    else:
        room_id = username
        new_room = Room(
            room_id=room_id,
            username=username,
            language=language,
            language_level=language_level
        )
        new_room.save()
        return redirect(url_for(endpoint="entry_checkpoint", room_id=room_id))


@app.route("/room/<string:room_id>/")
def enter_room(room_id):
    if room_id not in session:
        return redirect(url_for("entry_checkpoint", room_id=room_id))
    return render_template("chatroom.html", room_id=room_id, display_name=session[room_id]["name"],
                           mute_audio=session[room_id]["mute_audio"], mute_video=session[room_id]["mute_video"])


@app.route("/room/<string:room_id>/checkpoint/", methods=["GET", "POST"])
def entry_checkpoint(room_id):
    if request.method == "POST":
        display_name = request.form['display_name']
        mute_audio = request.form['mute_audio']
        mute_video = request.form['mute_video']
        session[room_id] = {"name": display_name, "mute_audio": mute_audio, "mute_video": mute_video}
        return redirect(url_for("enter_room", room_id=room_id))
    return render_template("chatroom_checkpoint.html", room_id=room_id)


@socketio.on("connect")
def on_connect():
    sid = request.sid
    print("New socket connected ", sid)
    

@socketio.on("join-room")
def on_join_room(data):
    sid = request.sid
    room_id = data["room_id"]
    display_name = session[room_id]["name"]
    
    # register sid to the room
    join_room(room_id)
    _room_of_sid[sid] = room_id
    _name_of_sid[sid] = display_name
    
    # broadcast to others in the room
    print("[{}] New member joined: {}<{}>".format(room_id, display_name, sid))
    emit("user-connect", {"sid": sid, "name": display_name}, broadcast=True, include_self=False, room=room_id)
    
    # add to user list maintained on server
    if room_id not in _users_in_room:
        _users_in_room[room_id] = [sid]
        emit("user-list", {"my_id": sid})   # send own id only
    else:
        usrlist = {u_id: _name_of_sid[u_id] for u_id in _users_in_room[room_id]}
        emit("user-list", {"list": usrlist, "my_id": sid})  # send list of existing users to the new member
        _users_in_room[room_id].append(sid)  # add new member to user list maintained on server

    print("\nusers: ", _users_in_room, "\n")


@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    room_id = _room_of_sid[sid]
    display_name = _name_of_sid[sid]

    print("[{}] Member left: {}<{}>".format(room_id, display_name, sid))
    emit("user-disconnect", {"sid": sid}, broadcast=True, include_self=False, room=room_id)

    _users_in_room[room_id].remove(sid)
    if len(_users_in_room[room_id]) == 0:
        _users_in_room.pop(room_id)

    _room_of_sid.pop(sid)
    _name_of_sid.pop(sid)

    print("\nusers: ", _users_in_room, "\n")


@socketio.on("data")
def on_data(data):
    sender_sid = data['sender_id']
    target_sid = data['target_id']
    if sender_sid != request.sid:
        print("[Not supposed to happen!] request.sid and sender_id don't match!!!")

    if data["type"] != "new-ice-candidate":
        print('{} message from {} to {}'.format(data["type"], sender_sid, target_sid))
    socketio.emit('data', data, room=target_sid)


if __name__ == "__main__":
    # with app.app_context():
    #     db.drop_all()
    # with app.app_context():
    #     db.create_all()
    socketio.run(app, debug=True)
