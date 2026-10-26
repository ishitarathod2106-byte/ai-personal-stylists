from colorthief import ColorThief

def analyze_outfit_color(image_path):
    print(f"Loading image: {image_path}...")
    
    # 1. Give the image to ColorThief
    color_thief = ColorThief(image_path)
    
    # 2. Get the main, most dominant color (Returns RGB values)
    dominant_color = color_thief.get_color(quality=1)
    
    print("-----------------------------------")
    print(f"The dominant RGB color is: {dominant_color}")
    print("-----------------------------------")
    
    # 3. Simple logic to guess the color family
    r, g, b = dominant_color
    
    if r > g and r > b:
        print("Verdict: This outfit is mostly RED/WARM-toned.")
    elif b > r and b > g:
        print("Verdict: This outfit is mostly BLUE/COOL-toned.")
    elif g > r and g > b:
        print("Verdict: This outfit is mostly GREEN-toned.")
    else:
        print("Verdict: This outfit has a mixed or neutral tone.")

# Run our function using the test image
analyze_outfit_color('test_outfit.jfif')