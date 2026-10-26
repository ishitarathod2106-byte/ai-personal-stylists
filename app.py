from flask import Flask, render_template, request, session, redirect, url_for
import os
import pymysql
import colorsys  
from colorthief import ColorThief
from PIL import Image
import requests

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback_secret_key')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- AIVEN DATABASE CONNECTION ---
def get_db_connection():
    return pymysql.connect(
        host='mysql-38dfe19d-ishitarathod2106-26d7.h.aivencloud.com',
        port=20270,        
        user='avnadmin',
        password=os.environ.get("AIVEN_PASSWORD"),  # <-- FIXED: Now securely pulls from Render
        database='defaultdb',
        ssl={'ssl': {}},              
        cursorclass=pymysql.cursors.DictCursor
    )

# --- ADVANCED SKIN TONE ALGORITHM ---
def get_skin_profile(r, g, b):
    luminance = (0.299 * r) + (0.587 * g) + (0.114 * b)
    if luminance > 180: depth = "Fair"
    elif luminance > 130: depth = "Medium"
    elif luminance > 80: depth = "Dark"
    else: depth = "Deep"

    if abs(r - b) < 25: undertone = "NEUTRAL"
    elif g > b + 15 and r < g + 35: undertone = "OLIVE"
    elif r > b + 30: undertone = "WARM"
    else: undertone = "COOL"
        
    return f"{depth} skin with {undertone.title()} undertones", undertone

# --- PERMANENT HSV COLOR ALGORITHM ---
def get_color_name_and_tone(r, g, b):
    h, s, v = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)
    h = h * 360  
    
    if v < 0.15: return "Black / Very Dark", "NEUTRAL"
    if v > 0.9 and s < 0.1: return "Pure White", "NEUTRAL"
    if s < 0.15:
        if v > 0.7: return "Light Gray", "NEUTRAL"
        if v < 0.4: return "Dark Gray / Charcoal", "NEUTRAL"
        return "Gray", "NEUTRAL"

    if h < 15 or h >= 345: base_color, tone = "Red / Pink", "WARM"
    elif 15 <= h < 45: base_color, tone = "Orange / Brown / Peach", "WARM"
    elif 45 <= h < 75: base_color, tone = "Yellow", "WARM"
    elif 75 <= h < 160: base_color, tone = "Green", "WARM" if h < 120 else "COOL"
    elif 160 <= h < 260: base_color, tone = "Blue", "COOL"
    elif 260 <= h < 315: base_color, tone = "Purple", "COOL"
    elif 315 <= h < 345: base_color, tone = "Pink / Magenta", "COOL"
    else: base_color, tone = "Mixed", "NEUTRAL"

    modifier = ""
    if v < 0.4: modifier = "Dark "
    elif v > 0.8 and s < 0.4: modifier = "Pale / Pastel "
    elif s < 0.4: modifier = "Muted / Faded "

    return modifier + base_color, tone

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    password = request.form['password']
    skin_img = request.files.get('skin_photo')
    
    if skin_img:
        skin_path = os.path.join(app.config['UPLOAD_FOLDER'], skin_img.filename)
        skin_img.save(skin_path)
        
        skin_thief = ColorThief(skin_path)
        skin_r, skin_g, skin_b = skin_thief.get_color(quality=1)
        full_profile, user_tone = get_skin_profile(skin_r, skin_g, skin_b)
        
        connection = get_db_connection()
        cursor = connection.cursor()
        sql = "INSERT INTO users (username, password, skin_tone) VALUES (%s, %s, %s, %s)"
        cursor.execute(sql, (username, password, user_tone))
        connection.commit()
        cursor.close()
        connection.close()
        
        session['username'] = username
        session['skin_tone'] = user_tone
        session['full_profile'] = full_profile 
        
    return redirect(url_for('home'))

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    
    connection = get_db_connection()
    cursor = connection.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
    user = cursor.fetchone()
    cursor.close()
    connection.close()
    
    if user:
        session['username'] = user['username']
        session['skin_tone'] = user['skin_tone']
        session['full_profile'] = f"Saved Profile ({user['skin_tone']} Undertones)"
        
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear() 
    return redirect(url_for('home'))

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'skin_tone' not in session:
        return "Please log in first!"
        
    outfit_img = request.files.get('outfit')
    
    if outfit_img:
        skin_filename = outfit_img.filename
        skin_path = os.path.join(app.config['UPLOAD_FOLDER'], skin_filename)
        outfit_img.save(skin_path)
        
        # --- HUGGING FACE MICROSERVICE (Replaces local rembg) ---
        HF_TOKEN = os.environ.get("HF_TOKEN") # Starts with hf_
        API_URL = "https://api-inference.huggingface.co/models/briaai/RMBG-1.4"
        headers = {"Authorization": f"Bearer {HF_TOKEN}"}
        
        with open(skin_path, 'rb') as f:
            response = requests.post(API_URL, headers=headers, data=f.read())
            
        if response.status_code == 200:
            nobg_filename = "nobg_" + skin_filename
            nobg_path = os.path.join(app.config['UPLOAD_FOLDER'], nobg_filename)
            with open(nobg_path, 'wb') as f:
                f.write(response.content)

            # Extract Colors 
            img = Image.open(nobg_path).convert("RGBA")
            img = img.resize((150, 150)) 
            colors = img.getcolors(maxcolors=25000)
            
            valid_colors = [(count, (r, g, b)) for count, (r, g, b, a) in colors if a > 200]
            valid_colors.sort(reverse=True)
            
            # DISTINCT COLOR FILTER
            top_3_colors = []
            for count, (r, g, b) in valid_colors:
                is_unique = True
                for _, (saved_r, saved_g, saved_b) in top_3_colors:
                    color_distance = ((r - saved_r)**2 + (g - saved_g)**2 + (b - saved_b)**2) ** 0.5
                    if color_distance < 60: 
                        is_unique = False
                        break
                if is_unique:
                    top_3_colors.append((count, (r, g, b)))
                if len(top_3_colors) == 3: break
            
            user_tone = session['skin_tone']
            
            # Build the UI Response dynamically
            report_html = f"<h3>Your Style Report (Your Tone: {user_tone}):</h3>"
            report_html += f"<p><b>What the AI sees (Background Erased):</b></p>"
            report_html += f"<img src='/static/uploads/{nobg_filename}' style='border: 2px solid black; max-width: 250px; background-color: #f0f0f0;'><br><br>"
            report_html += "<p><b>Dominant Outfit Colors Detected:</b></p><ul>"
            
            for count, (r, g, b) in top_3_colors:
                color_name, outfit_tone = get_color_name_and_tone(r, g, b)
                if outfit_tone == "NEUTRAL": advice = "Great neutral, very versatile."
                elif user_tone == outfit_tone: advice = "PERFECT match for your skin tone!"
                else: advice = "This tone slightly clashes with your complexion."
                report_html += f"<li><b>{color_name}</b> (RGB: {r},{g},{b}) - {advice}</li>"
            
            report_html += "</ul><br><a href='/'>Go Back</a>"
            
            try:
                if os.path.exists(skin_path): os.remove(skin_path)
            except: pass
                
            return report_html
        else:
            return f"Error with AI API: {response.status_code} - {response.text}"
        
    return "Error uploading file."

if __name__ == '__main__':
    app.run(debug=True)