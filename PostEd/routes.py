import os
import secrets
from PIL import Image
from flask import render_template, redirect, url_for, flash, request, abort
from PostEd.forms import (RegistrationForm, LoginForm, UpdateAccountForm,
                          NewPostForm, ResetRequestForm, ResetPasswordForm)
from PostEd import app, db, bcrypt, mail
from flask_mail import Message
from PostEd.models import User, Post
from flask_login import login_user, current_user, logout_user, login_required


@app.route("/")
@app.route("/home")
def home():
    page = request.args.get('page', 1, type=int)
    posts = Post.query.order_by(Post.date_posted.desc()).paginate(per_page=10, page=page)
    return render_template("home.html", posts=posts)


@app.route("/about")
def about():
    return render_template("about.html", title='About')


@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=username, email=email, password=password)
        db.session.add(user)
        db.session.commit()
        flash(f'Account created. You can login.', 'success')
        return redirect(url_for('login'))
    return render_template("register.html", form=form, title='register')


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('home'))
        else:
            flash(f'Login Unsuccessful. Please Check Email and Password.', 'danger')
    return render_template("login.html", form=form, title='login')


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))


def save_picture(form_picture, curr_image):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    file_name = random_hex + f_ext
    file_path = os.path.join(app.root_path, 'static/profile_pics', file_name)
    curr_path = os.path.join(app.root_path, 'static/profile_pics', curr_image)
    im = Image.open(form_picture)
    im.thumbnail((125, 125))
    im.save(file_path)
    if curr_image != 'default.jpg' and os.path.exists(curr_path):
        os.remove(curr_path)
    return file_name


@login_required
@app.route("/account", methods=["GET", "POST"])
def account():
    image_file = url_for('static', filename=f'profile_pics/{current_user.image}')
    form = UpdateAccountForm()
    if form.validate_on_submit():
        if form.picture.data:
            picture = save_picture(form.picture.data, current_user.image)
            current_user.image = picture
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash("Your account has been updated!", 'success')
        return redirect(url_for('account'))
    elif request.method == "GET":
        form.username.data = current_user.username
        form.email.data = current_user.email
    return render_template("account.html", title='Account', image_file=image_file, form=form, legend="Account Info")


@login_required
@app.route("/post/new", methods=['GET', 'POST'])
def new_post():
    form = NewPostForm()
    if form.validate_on_submit():
        post = Post(title=form.title.data, content=form.content.data, author=current_user)
        db.session.add(post)
        db.session.commit()
        flash("Your Post has been uploaded!", 'success')
        return redirect(url_for('home'))
    return render_template("create_post.html", title='New Post', form=form, legend="New Post")


@app.route("/post/<int:post_id>")
def post(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template("post.html", title="Post", post=post)


@login_required
@app.route("/post/<int:post_id>/update", methods=["GET", "POST"])
def update_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    form = NewPostForm()
    if form.validate_on_submit():
        post.title = form.title.data
        post.content = form.content.data
        db.session.commit()
        flash("Post updated!!", 'success')
        return redirect(url_for('post', post_id=post.id))
    elif request.method == "GET":
        form.title.data = post.title
        form.content.data = post.content
        form.submit.label.text = 'Update'
    return render_template("create_post.html", title="Update Post", form=form, legend="Update Post")


@login_required
@app.route('/post/<post_id>/delete', methods=['Post', 'GET'])
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash("Post Deleted.", 'success')
    return redirect(url_for('home'))


@app.route("/user/<string:username>")
def user_post(username):
    user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get('page', 1, type=int)
    posts = Post.query.filter_by(author=user).order_by(Post.date_posted.desc()).paginate(per_page=10, page=page)
    image_file = url_for('static', filename=f'profile_pics/{user.image}')
    return render_template("user_posts.html", title=user.username, posts=posts, user=user, image_file=image_file)


def send_email(user):
    token = user.get_reset_token()
    msg = Message('Password Reset Request', sender='demo@gmail.com', recipients=[user.email])

    msg.body = f'''To reset password, visit following link:
{url_for('reset_token', token=token, _external=True)}

If you did not make this request simply ignore this email and no changes will be made.    
    '''
    mail.send(msg)


@app.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = ResetRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        send_email(user)
        flash(f'Reset link has been sent to your email.', 'info')
        return redirect(url_for('login'))
    return render_template("reset_request.html", form=form, title='Reset Password')


@app.route("/reset_password/<string:token>", methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    user = User.verify_reset_token(token)
    if user is None:
        flash("Your token is invalid or expired.", 'warning')
        return redirect(url_for('reset_request'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user.password = password
        db.session.commit()
        flash(f'Your password has been updated. You can login now.', 'success')
        return redirect(url_for('login'))

    return render_template("reset_token.html", form=form, title='Reset Password')

