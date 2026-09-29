import os,secrets,datetime,smtplib
from email.message import EmailMessage
from functools import wraps
from flask import Flask,render_template,request,redirect,url_for,session,flash,jsonify,abort
from werkzeug.security import generate_password_hash,check_password_hash
import database
try:
 from authlib.integrations.flask_client import OAuth
except Exception:
 OAuth=None
app=Flask(__name__)
app.secret_key=os.getenv("SECRET_KEY","CHANGE_ME_IN_ENV")
FEATURES={'ecommerce': False, 'services': False, 'restaurant': False, 'school': False, 'auth': False, 'admin': True, 'orders': True, 'cart': True, 'checkout': True, 'reviews': True, 'contact': True, 'email_verification': True, 'google_login': True, 'facebook_login': True}
SITE_TITLE='Online Shoping'
database.init_db()

def current_user():
 uid=session.get("user_id")
 if not uid:return None
 db=database.get_db(); u=db.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone(); db.close(); return u

@app.context_processor
def ctx(): return {"user":current_user(),"site_title":SITE_TITLE,"features":FEATURES,"cart_count":len(session.get("cart",[]))}

def login_required(fn):
 @wraps(fn)
 def w(*a,**k):
  if not session.get("user_id"): flash("Please login first.","warning"); return redirect(url_for("login",next=request.path))
  return fn(*a,**k)
 return w

def verified_required(fn):
 @wraps(fn)
 def w(*a,**k):
  u=current_user()
  if not u:return redirect(url_for("login"))
  if not u["email_verified"]: flash("Please verify your email first.","warning"); return redirect(url_for("verify_notice"))
  return fn(*a,**k)
 return w

def admin_required(fn):
 @wraps(fn)
 def w(*a,**k):
  u=current_user()
  if not u or u["role"]!="admin": abort(403)
  return fn(*a,**k)
 return w

def send_email(to,subject,body):
 host=os.getenv("MAIL_SERVER",""); user=os.getenv("MAIL_USERNAME",""); pwd=os.getenv("MAIL_PASSWORD",""); port=int(os.getenv("MAIL_PORT","587")); sender=os.getenv("MAIL_DEFAULT_SENDER",user)
 if not host or not user or not pwd:
  print("\n[EMAIL NOT CONFIGURED]\nTO:",to,"\n",body,"\n"); return False
 msg=EmailMessage(); msg["From"]=sender; msg["To"]=to; msg["Subject"]=subject; msg.set_content(body)
 try:
  with smtplib.SMTP(host,port,timeout=20) as s: s.starttls(); s.login(user,pwd); s.send_message(msg)
  return True
 except Exception as e: print("Email error:",e); return False

def create_token(user_id):
 token=secrets.token_urlsafe(32); expires=(datetime.datetime.utcnow()+datetime.timedelta(hours=24)).isoformat(); db=database.get_db(); db.execute("INSERT INTO email_verifications(user_id,token,expires_at) VALUES(?,?,?)",(user_id,token,expires)); db.commit(); db.close(); return token

@app.route("/")
def index():
 db=database.get_db(); p=db.execute("SELECT * FROM products WHERE active=1 ORDER BY id DESC LIMIT 8").fetchall(); db.close(); return render_template("index.html",products=p)

@app.route("/products")
def products():
 cat=request.args.get("category","all"); db=database.get_db(); p=db.execute("SELECT * FROM products WHERE active=1"+("" if cat=="all" else " AND category=?")+" ORDER BY id DESC",(() if cat=="all" else (cat,))).fetchall(); cats=db.execute("SELECT DISTINCT category FROM products WHERE active=1 AND category IS NOT NULL ORDER BY category").fetchall(); db.close(); return render_template("products.html",products=p,categories=cats,selected_category=cat)

@app.route("/product/<int:product_id>")
def product_detail(product_id):
 db=database.get_db(); p=db.execute("SELECT * FROM products WHERE id=? AND active=1",(product_id,)).fetchone(); r=db.execute("SELECT reviews.*,users.name FROM reviews JOIN users ON users.id=reviews.user_id WHERE product_id=? ORDER BY reviews.id DESC",(product_id,)).fetchall(); db.close();
 if not p: abort(404)
 return render_template("product_detail.html",product=p,reviews=r)

@app.route("/cart")
def cart():
 ids=session.get("cart",[]); db=database.get_db(); p=[]
 for i in ids:
  x=db.execute("SELECT * FROM products WHERE id=? AND active=1",(i,)).fetchone()
  if x:p.append(x)
 db.close(); return render_template("cart.html",products=p)

@app.post("/cart/add/<int:product_id>")
def add_cart(product_id):
 db=database.get_db(); x=db.execute("SELECT id FROM products WHERE id=? AND active=1",(product_id,)).fetchone(); db.close()
 if not x: flash("Product not found.","danger"); return redirect(url_for("products"))
 c=session.get("cart",[]); c.append(product_id); session["cart"]=c; flash("Product added to cart.","success"); return redirect(request.referrer or url_for("products"))

@app.post("/cart/remove/<int:product_id>")
def remove_cart(product_id):
 c=session.get("cart",[]);
 if product_id in c:c.remove(product_id)
 session["cart"]=c; return redirect(url_for("cart"))

@app.route("/signup",methods=["GET","POST"])
def signup():
 if request.method=="GET": return render_template("signup.html")
 name=request.form.get("name","").strip(); email=request.form.get("email","").strip().lower(); password=request.form.get("password",""); confirm=request.form.get("confirm_password","")
 if not name or not email or not password or "@" not in email or len(password)<8 or password!=confirm:
  flash("Please enter valid signup details and matching password (8+ characters).","danger"); return render_template("signup.html")
 db=database.get_db(); existing=db.execute("SELECT id FROM users WHERE email=?",(email,)).fetchone()
 if existing: db.close(); flash("Email already registered. Please login.","warning"); return redirect(url_for("login"))
 cur=db.execute("INSERT INTO users(name,email,password_hash,role,email_verified) VALUES(?,?,?, 'customer',0)",(name,email,generate_password_hash(password))); uid=cur.lastrowid; db.commit(); db.close()
 token=create_token(uid); link=url_for("verify_email",token=token,_external=True); send_email(email,SITE_TITLE+" - Verify Email",f"Hello {name},\n\nVerify your email here:\n{link}\n\nLink expires in 24 hours.")
 session["user_id"]=uid; flash("Account created. Email verification link bhej diya gaya hai.","success"); return redirect(url_for("verify_notice"))

@app.route("/login",methods=["GET","POST"])
def login():
 if request.method=="GET": return render_template("login.html")
 email=request.form.get("email","").strip().lower(); password=request.form.get("password",""); db=database.get_db(); u=db.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone(); db.close()
 if not u or not u["password_hash"] or not check_password_hash(u["password_hash"],password): flash("Invalid email or password.","danger"); return render_template("login.html")
 session["user_id"]=u["id"]
 if not u["email_verified"]: return redirect(url_for("verify_notice"))
 return redirect(request.args.get("next") or url_for("dashboard"))

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("index"))

@app.route("/verify-notice")
def verify_notice(): return render_template("verify_notice.html")

@app.route("/verify-email/<token>")
def verify_email(token):
 db=database.get_db(); row=db.execute("SELECT * FROM email_verifications WHERE token=? AND used=0",(token,)).fetchone()
 if not row: db.close(); flash("Invalid verification link.","danger"); return redirect(url_for("login"))
 try: expired=datetime.datetime.utcnow()>datetime.datetime.fromisoformat(row["expires_at"])
 except Exception: expired=True
 if expired: db.close(); flash("Verification link expired.","danger"); return redirect(url_for("login"))
 db.execute("UPDATE users SET email_verified=1 WHERE id=?",(row["user_id"],)); db.execute("UPDATE email_verifications SET used=1 WHERE id=?",(row["id"],)); db.commit(); db.close(); session["user_id"]=row["user_id"]; flash("Email verified successfully.","success"); return redirect(url_for("dashboard"))

# OAuth is optional until credentials are placed in .env.
oauth=OAuth(app) if OAuth else None
if oauth:
 gid=os.getenv("GOOGLE_CLIENT_ID"); gs=os.getenv("GOOGLE_CLIENT_SECRET")
 if gid and gs: oauth.register(name="google",client_id=gid,client_secret=gs,server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",client_kwargs={"scope":"openid email profile"})
 fid=os.getenv("FACEBOOK_CLIENT_ID"); fs=os.getenv("FACEBOOK_CLIENT_SECRET")
 if fid and fs: oauth.register(name="facebook",client_id=fid,client_secret=fs,access_token_url="https://graph.facebook.com/oauth/access_token",authorize_url="https://www.facebook.com/dialog/oauth",api_base_url="https://graph.facebook.com/",client_kwargs={"scope":"email"})

@app.route("/auth/google")
def google_login():
 if not oauth or "google" not in oauth._clients: flash("Google OAuth credentials .env mein configure karein.","warning"); return redirect(url_for("signup"))
 return oauth.google.authorize_redirect(url_for("google_callback",_external=True))

@app.route("/auth/google/callback")
def google_callback():
 try:
  token=oauth.google.authorize_access_token(); info=token.get("userinfo") or oauth.google.get("https://openidconnect.googleapis.com/v1/userinfo").json(); email=str(info.get("email","")).lower().strip(); name=info.get("name") or email.split("@")[0]; gid=info.get("sub")
  if not email: raise ValueError("Google email missing")
  db=database.get_db(); u=db.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone()
  if u: uid=u["id"]; db.execute("UPDATE users SET google_id=?,email_verified=1,name=? WHERE id=?",(gid,name,uid))
  else: uid=db.execute("INSERT INTO users(name,email,role,email_verified,google_id) VALUES(?,?, 'customer',1,?)",(name,email,gid)).lastrowid
  db.commit(); db.close(); session["user_id"]=uid; return redirect(url_for("dashboard"))
 except Exception as e: print("Google OAuth error:",e); flash("Google login error.","danger"); return redirect(url_for("signup"))

@app.route("/auth/facebook")
def facebook_login():
 if not oauth or "facebook" not in oauth._clients: flash("Facebook OAuth credentials .env mein configure karein.","warning"); return redirect(url_for("signup"))
 return oauth.facebook.authorize_redirect(url_for("facebook_callback",_external=True))

@app.route("/auth/facebook/callback")
def facebook_callback():
 try:
  token=oauth.facebook.authorize_access_token(); info=oauth.facebook.get("/me?fields=id,name,email",token=token).json(); email=str(info.get("email","")).lower().strip(); name=info.get("name") or "Facebook User"; fid=info.get("id")
  if not email: raise ValueError("Facebook email missing")
  db=database.get_db(); u=db.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone()
  if u: uid=u["id"]; db.execute("UPDATE users SET facebook_id=?,email_verified=1,name=? WHERE id=?",(fid,name,uid))
  else: uid=db.execute("INSERT INTO users(name,email,role,email_verified,facebook_id) VALUES(?,?, 'customer',1,?)",(name,email,fid)).lastrowid
  db.commit(); db.close(); session["user_id"]=uid; return redirect(url_for("dashboard"))
 except Exception as e: print("Facebook OAuth error:",e); flash("Facebook login error.","danger"); return redirect(url_for("signup"))

@app.route("/dashboard")
@login_required
def dashboard():
 u=current_user(); db=database.get_db(); orders=db.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC",(u["id"],)).fetchall(); services=db.execute("SELECT * FROM service_requests WHERE user_id=? ORDER BY id DESC",(u["id"],)).fetchall(); db.close(); return render_template("dashboard.html",orders=orders,services=services)

@app.route("/profile",methods=["GET","POST"])
@login_required
def profile():
 u=current_user()
 if request.method=="POST":
  db=database.get_db(); db.execute("UPDATE users SET name=?,phone=?,address=?,city=?,province=?,postal_code=? WHERE id=?",(request.form.get("name",""),request.form.get("phone",""),request.form.get("address",""),request.form.get("city",""),request.form.get("province",""),request.form.get("postal_code",""),u["id"])); db.commit(); db.close(); flash("Profile updated.","success"); return redirect(url_for("profile"))
 return render_template("profile.html",profile_user=u)

@app.route("/checkout",methods=["GET","POST"])
@login_required
def checkout():
 ids=session.get("cart",[]);
 if not ids: flash("Cart empty hai.","warning"); return redirect(url_for("products"))
 db=database.get_db(); products=[]
 for pid in ids:
  p=db.execute("SELECT * FROM products WHERE id=? AND active=1",(pid,)).fetchone()
  if p: products.append(p)
 if not products: db.close(); session["cart"]=[]; flash("Cart products nahi milay.","warning"); return redirect(url_for("products"))
 subtotal=sum(float(p["price"]) for p in products); delivery=0 if subtotal>=5000 else 250; discount=0; tax=0; total=subtotal+delivery-discount+tax
 if request.method=="GET": db.close(); return render_template("checkout.html",products=products,subtotal=subtotal,delivery_fee=delivery,discount=discount,tax=tax,total=total)
 u=current_user(); name=request.form.get("name","").strip(); email=request.form.get("email","").strip().lower(); phone=request.form.get("phone","").strip(); address=request.form.get("address","").strip(); city=request.form.get("city","").strip(); province=request.form.get("province","").strip()
 payment_method=request.form.get("payment_method","Cash on Delivery").strip() or "Cash on Delivery"
 if payment_method not in {"Cash on Delivery","Bank Transfer","Online Payment"}: payment_method="Cash on Delivery"
 if not all([name,email,phone,address,city,province]) or "@" not in email:
  db.close(); flash("Name, valid email, phone, address, city and province required hain.","danger"); return redirect(url_for("checkout"))
 order_no="ORD-"+datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")+"-"+secrets.token_hex(2).upper()
 try:
  cur=db.execute("""INSERT INTO orders(order_number,user_id,customer_name,customer_email,phone,alternate_phone,country,province,city,area,address,house_number,postal_code,delivery_instructions,payment_method,payment_status,transaction_id,subtotal,discount,delivery_fee,tax,total,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(order_no,u["id"],name,email,phone,request.form.get("alternate_phone",""),request.form.get("country","Pakistan"),province,city,request.form.get("area",""),address,request.form.get("house_number",""),request.form.get("postal_code",""),request.form.get("delivery_instructions",""),payment_method,"Pending",request.form.get("transaction_id",""),subtotal,discount,delivery,tax,total,"Pending"))
  oid=cur.lastrowid
  for p in products:
   db.execute("INSERT INTO order_items(order_id,product_id,product_name,product_image,quantity,price,line_total) VALUES(?,?,?,?,?,?,?)",(oid,p["id"],p["name"],p["image"],1,float(p["price"]),float(p["price"])))
  db.commit()
 except Exception as e:
  db.rollback(); db.close(); print("Order creation error:",repr(e)); flash("Order place nahi ho saka. Flask terminal mein exact error check karein.","danger"); return redirect(url_for("checkout"))
 db.close(); session["cart"]=[]; flash("Order "+order_no+" successfully place ho gaya.","success"); return redirect(url_for("order_detail",order_id=oid))
@app.route("/orders")
@login_required
def orders():
 u=current_user(); db=database.get_db(); rows=db.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC",(u["id"],)).fetchall(); db.close(); return render_template("orders.html",orders=rows)

@app.route("/order/<int:order_id>")
@login_required
def order_detail(order_id):
 u=current_user(); db=database.get_db(); order=db.execute("SELECT * FROM orders WHERE id=? AND user_id=?",(order_id,u["id"])).fetchone();
 if not order: db.close(); abort(404)
 items=db.execute("SELECT * FROM order_items WHERE order_id=?",(order_id,)).fetchall(); db.close(); return render_template("order_detail.html",order=order,items=items)

@app.route("/services",methods=["GET","POST"])
def services():
 if request.method=="GET": return render_template("services.html")
 data=[request.form.get(x,"").strip() for x in ["name","email","phone","service_name"]]
 if not all(data): flash("Name, email, phone and service required hain.","danger"); return redirect(url_for("services"))
 db=database.get_db(); db.execute("INSERT INTO service_requests(user_id,customer_name,email,phone,service_name,address,city,preferred_date,preferred_time,description) VALUES(?,?,?,?,?,?,?,?,?,?)",(session.get("user_id"),request.form.get("name"),request.form.get("email"),request.form.get("phone"),request.form.get("service_name"),request.form.get("address"),request.form.get("city"),request.form.get("preferred_date"),request.form.get("preferred_time"),request.form.get("description"))); db.commit(); db.close(); flash("Service request submit ho gayi.","success"); return redirect(url_for("services"))

@app.route("/contact",methods=["GET","POST"])
def contact():
 if request.method=="GET": return render_template("contact.html")
 name=request.form.get("name","").strip(); email=request.form.get("email","").strip(); message=request.form.get("message","").strip()
 if not name or not email or not message: flash("Name, email and message required hain.","danger"); return redirect(url_for("contact"))
 db=database.get_db(); db.execute("INSERT INTO messages(user_id,name,email,phone,subject,message) VALUES(?,?,?,?,?,?)",(session.get("user_id"),name,email,request.form.get("phone"),request.form.get("subject"),message)); db.commit(); db.close(); flash("Message sent successfully.","success"); return redirect(url_for("contact"))

@app.post("/product/<int:product_id>/review")
@login_required
@verified_required
def review(product_id):
 u=current_user(); rating=max(1,min(5,int(request.form.get("rating","5")))); comment=request.form.get("comment",""); db=database.get_db(); old=db.execute("SELECT id FROM reviews WHERE product_id=? AND user_id=?",(product_id,u["id"])).fetchone()
 if old: db.execute("UPDATE reviews SET rating=?,comment=? WHERE id=?",(rating,comment,old["id"]))
 else: db.execute("INSERT INTO reviews(product_id,user_id,rating,comment) VALUES(?,?,?,?)",(product_id,u["id"],rating,comment))
 db.commit(); db.close(); return redirect(url_for("product_detail",product_id=product_id))

@app.route("/admin")
@admin_required
def admin():
 db=database.get_db(); stats={"users":db.execute("SELECT COUNT(*) c FROM users WHERE role='customer'").fetchone()["c"],"orders":db.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"],"services":db.execute("SELECT COUNT(*) c FROM service_requests").fetchone()["c"],"messages":db.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"],"revenue":db.execute("SELECT COALESCE(SUM(total),0) total FROM orders WHERE status!='Cancelled'").fetchone()["total"]}; ro=db.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 50").fetchall(); rs=db.execute("SELECT * FROM service_requests ORDER BY id DESC LIMIT 50").fetchall(); rm=db.execute("SELECT * FROM messages ORDER BY id DESC LIMIT 50").fetchall(); db.close(); return render_template("admin.html",stats=stats,recent_orders=ro,recent_services=rs,recent_messages=rm)

@app.post("/admin/order/<int:order_id>/status")
@admin_required
def admin_order_status(order_id):
 status=request.form.get("status","Pending"); allowed={"Pending","Confirmed","Processing","Shipped","Out for Delivery","Delivered","Cancelled"}; status=status if status in allowed else "Pending"; db=database.get_db(); db.execute("UPDATE orders SET status=? WHERE id=?",(status,order_id)); db.commit(); db.close(); return redirect(url_for("admin"))

@app.post("/admin/service/<int:service_id>/status")
@admin_required
def admin_service_status(service_id):
 status=request.form.get("status","Pending"); allowed={"Pending","Confirmed","In Progress","Completed","Cancelled"}; status=status if status in allowed else "Pending"; db=database.get_db(); db.execute("UPDATE service_requests SET status=? WHERE id=?",(status,service_id)); db.commit(); db.close(); return redirect(url_for("admin"))

@app.get("/api/health")
def health(): return jsonify({"status":"ok","features":FEATURES,"database":database.DB_PATH})

@app.get("/api/products")
def api_products():
 db=database.get_db(); rows=db.execute("SELECT id,name,category,description,price,image,stock FROM products WHERE active=1 ORDER BY id DESC").fetchall(); db.close(); return jsonify([dict(x) for x in rows])

@app.errorhandler(403)
def e403(e): return render_template("403.html"),403
@app.errorhandler(404)
def e404(e): return render_template("404.html"),404
@app.errorhandler(500)
def e500(e): return render_template("500.html"),500

if __name__=="__main__": app.run(host=os.getenv("HOST","127.0.0.1"),port=int(os.getenv("PORT","5000")),debug=False)
