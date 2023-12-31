from flask import Flask, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentsForm, MyForm, RatingForm
from flask_gravatar import Gravatar
from functools import wraps
import os
from datetime import datetime
import requests

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap5(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("POSTGRES_DATABASE_URL", "sqlite:///blog.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


##CONFIGURE TABLES
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    name = db.Column(db.String(250), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    posts = db.relationship("BlogPost", back_populates="author", lazy=True)
    comments = db.relationship("Comment", back_populates="user")

    def __repr__(self):
        return f"{self.name}"


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    author = db.relationship("User", back_populates="posts", lazy=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments = db.relationship("Comment", back_populates="parent_post")

    def __repr__(self):
        return f"<BlogPost {self.title}>"


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user = db.relationship("User", back_populates="comments")
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"), nullable=False)
    parent_post = db.relationship("BlogPost", back_populates="comments")
    text = db.Column(db.String(500), nullable=False)


class Movies(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String, nullable=False)
    rating = db.Column(db.Float)
    ranking = db.Column(db.Integer)
    review = db.Column(db.String(40))
    img_url = db.Column(db.String(250), nullable=False)


with app.app_context():
    db.create_all()

year = datetime.now().year


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You need to be an admin to access this page.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts, year=year)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    new_user = User()
    if form.validate_on_submit():
        email = form.email.data
        user = User.query.filter_by(email=email).first()
        if user:
            flash("This email address is already registered.")
            return redirect(url_for("register"))
        else:
            new_user.email = email
            new_user.password = generate_password_hash(form.password.data)
            new_user.name = form.name.data
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for("get_all_posts"))

    return render_template("register.html", form=form)


def make_admin(user_email):
    with app.app_context():
        user = User.query.filter_by(email=user_email).first()
        user.is_admin = True
        db.session.commit()


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        user = User.query.filter_by(email=email).first()
        if user:
            if check_password_hash(user.password, password):
                login_user(user)
                return redirect(url_for("get_all_posts"))
            else:
                flash("Wrong password!")
        else:
            flash("Email address doesn't exist!")

    return render_template("login.html", form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    form = CommentsForm()
    requested_post = BlogPost.query.get(post_id)
    comments = Comment.query.filter_by(post_id=post_id).all()
    if form.validate_on_submit():
        if current_user.is_authenticated:
            new_comment = Comment(
                author_id=current_user.id,
                parent_post=requested_post,
                text=form.comment.data
            )
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for("show_post", post_id=post_id))
        else:
            flash("You need to login to comment.")
            return redirect(url_for("login"))
    return render_template("post.html", post=requested_post, form=form, comments=comments)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=["GET", "POST"])
@admin_required
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y"),
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_required
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@admin_required
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


url = "https://api.themoviedb.org/3/search/movie"
id_url = "https://api.themoviedb.org/3/movie/"
img_url_prefix = "https://image.tmdb.org/t/p/w600_and_h900_bestv2"
thm_prefix = "https://image.tmdb.org/t/p/w94_and_h141_bestv2/"

headers = {
    "accept": "application/json",
    "Authorization": os.environ.get("TMDB_API")
}


@app.route("/movies")
def movie_home():
    movies_list = db.session.execute(db.select(Movies).order_by(Movies.ranking)).scalars()
    return render_template("movies.html", movies_list=movies_list, year=year)


@app.route("/add", methods=["POST", "GET"])
def add():
    form = MyForm()
    if form.validate_on_submit():
        parameter = {
            "query": form.title.data,
        }
        response = requests.get(url, headers=headers, params=parameter).json()["results"]
        return render_template("result.html", response=response, prefix=thm_prefix)

    return render_template("add.html", form=form)


@app.route("/new/id=<id>", methods=["POST", "GET"])
def add_movie(id):
    movie_link = f"{id_url}{id}"
    if request.method == "GET":
        response = requests.get(movie_link, headers=headers).json()
        new_movie = Movies(
            title=response["title"],
            year=response["release_date"].split("-")[0],
            description=response["overview"],
            rating=0,
            ranking=0,
            review="none",
            img_url=f"{img_url_prefix}{response['poster_path']}",
        )
        db.session.add(new_movie)
        db.session.commit()
        find = db.one_or_404(db.select(Movies).filter_by(title=response["title"]))
        movie_id = find.id
        return redirect(url_for("update", id=movie_id))


@app.route("/update/id=<id>", methods=["POST", "GET"])
def update(id):
    form = RatingForm()
    update_movie = db.get_or_404(Movies, id)
    if form.validate_on_submit():
        update_movie.rating = form.rating.data
        update_movie.ranking = form.ranking.data
        update_movie.review = form.review.data
        db.session.commit()
        return redirect(url_for("movie_home"))
    return render_template("update.html", form=form, update_movie=update_movie)


@app.route("/movie/<int:id>/delete", methods=["GET", "POST"])
def movie_delete(id):
    delete = db.get_or_404(Movies, id)
    if request.method == "GET":
        db.session.delete(delete)
        db.session.commit()
        return redirect(url_for("movie_home"))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
