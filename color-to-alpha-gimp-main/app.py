'''
Application for testing the GIMP color to alpha algorithm

Maverick Reynolds
07.18.2023

'''

from PIL import Image
import streamlit as st
import col_to_alpha as cta
from io import BytesIO
import numpy as np

# For downloading the new image
def convert_image(img):
    buf = BytesIO()
    img.save(buf, format='PNG')
    byte_im = buf.getvalue()
    return byte_im


# Color conversion functions
def tuple_to_hex(tup):
    return f'#{tup[0]:02x}{tup[1]:02x}{tup[2]:02x}'.upper()

def hex_to_tuple(hex: str):
    hex = hex.lstrip('#')
    return tuple(int(hex[i:i+2], 16) for i in (0, 2, 4))


# To get the top colors in the image
def get_pixel_distribution(img):
    width, height = img.size
    counter = dict()

    # Count the number of pixels of each color
    for h in range(height):
        for w in range(width):
            pix = img.getpixel((w, h))
            if pix not in counter:
                counter[pix] = 1
            else:
                counter[pix] += 1

    # Sort the dictionary by value, highest to lowest
    counter = sorted(counter.items(), key=lambda x: x[1], reverse=True)
    return counter



def main():
    # Set up the page
    st.set_page_config(page_title='GIMP Color to Alpha Algorithm', page_icon='🎨', layout='wide')

    # Write a title and description
    st.title('GIMP Color to Alpha Algorithm 🎨')
    st.write("Upload an image and pick a color to see the algorithm in action! Don't forget to adjust the transparency and opacity thresholds to produce different results. The algorithm works by smoothly transitioning all colors that fall between the thresholds from opaque to transparent depending on how close they are to the selected color.")
    st.markdown("You can read more about how the algorithm works [here](https://medium.com/@mcreynolds02/how-gimps-color-to-alpha-tool-works-82372367afcd).")

    # Sidebar for upload and options
    st.sidebar.title('Upload an Image')
    file = st.sidebar.file_uploader('Original image', type=['png', 'jpg', 'jpeg', 'webp'])
    if file is None:
        img = Image.open('colExp.png')
    else:
        img = Image.open(file)

    # User settings
    st.sidebar.title('Settings :gear:')
    shape = st.sidebar.selectbox('Shape (used for calculating distance in RGB-space)', ['sphere', 'cube'])
    interpolation = st.sidebar.selectbox('Interpolation', ['linear', 'power', 'root', 'smooth', 'inverse-sin'])

    top_threshold_bound = 255 if shape == 'cube' else 442
    transparency_threshold = st.sidebar.slider('Transparency Threshold', 0, top_threshold_bound, 18)
    opacity_threshold = st.sidebar.slider('Opacity Threshold', 0, top_threshold_bound, 193)

    # Background replacement option
    if (use_background := st.sidebar.checkbox('Background Replacement')):
        background_color = st.sidebar.color_picker('Background Color', '#10EAEC')
        bg = Image.new('RGBA', img.size, background_color)

    # Color selection
    st.sidebar.title('Color Selection')
    color = '#FFFFFF'

    # Show the top colors in the image
    if st.sidebar.checkbox('Use top color in image'):
        top_colors = get_pixel_distribution(img)[0][0]
        color = tuple_to_hex(top_colors)

    color = st.sidebar.color_picker('Color', color)

    if st.sidebar.button('Get top colors from image'):
        NUM = 8
        top_colors = get_pixel_distribution(img)[0:NUM]
        colsb1, colsb2 = st.sidebar.columns(2)
        colsb2.write('\n')

        for i in range(0, NUM):
            colsb1.color_picker(tuple_to_hex(top_colors[i][0]), tuple_to_hex(top_colors[i][0]))
            colsb2.write(top_colors[i][1])
            colsb2.write('\n')
            colsb2.write('\n')


    # Main content on the page
    col1, col2 = st.columns(2)

    col1.subheader("Original Image 🖼️")
    col1.image(img)

    col2.subheader("Color to Alpha applied :wrench:")
    cta_arr = cta.color_to_alpha(np.array(img), hex_to_tuple(color), transparency_threshold, opacity_threshold, shape=shape, interpolation=interpolation)
    cta_img = Image.fromarray(cta_arr, 'RGBA')

    if use_background:
        cta_img = Image.alpha_composite(bg, cta_img)

    col2.image(cta_img)

    # Add download button
    col2.download_button('Download Image', convert_image(cta_img), file_name='color_to_alpha.png', mime='image/png')

if __name__ == '__main__':
    main()
