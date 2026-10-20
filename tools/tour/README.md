# The tour video

Makes the 90 second video on the home page from the demo. Two steps, so the video can be made again whenever the setup page changes.

1. **capture.mjs** walks through the demo in a real browser (Google Chrome through `puppeteer-core`). For every click it saves a picture before, with the pointer over the button, and after, plus where each button is. The pictures are 2560 x 1440, so zooming in stays sharp.
2. **compose.py** turns the pictures into a 1920 x 1080 video. The story is written as plain steps at the bottom of the file: move to this button, click, zoom on that list, say this in a caption.
   * The pointer moves along a curve with a small overshoot and a pause before the click, never in a straight line.
   * The camera only zooms where there is something to look at, scrolls to a button that is out of view, and never moves while the pointer is clicking.
   * The captions are short, plain sentences.

## Make it

```bash
python3 tools/build_site.py
(cd site && python3 -m http.server 8765) &          # serve the demo
cd tools/tour && npm install && cd ../..             # once
node tools/tour/capture.mjs tour-work                # the pictures, about 3 minutes
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --window-size=1920,1080 \\
  --virtual-time-budget=6000 --screenshot=tour-work/endcard.png "file://$PWD/tools/tour/endcard.html"
python3 tools/tour/compose.py tour-work landing/media/tour.mp4     # about 3 minutes
```

Needs Node, Python with Pillow (`pip install pillow`), ffmpeg and Google Chrome. The `tour-work` folder holds about 40 MB of pictures: delete it afterwards.

To change the story, edit the steps in `compose.py`. To change what is clicked, edit `capture.mjs`, and capture again.
