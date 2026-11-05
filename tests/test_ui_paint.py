import sys
import pytest
from PyQt6.QtWidgets import QApplication

def test_hud_canvas_paint_all_states():
    from ui import HudCanvas
    app = QApplication.instance() or QApplication(sys.argv)
    
    canvas = HudCanvas("face.png")
    canvas.resize(400, 400)
    canvas.show()

    states = ["THINKING", "PROCESSING", "LISTENING", "SLEEPING", "ASLEEP", "IDLE"]
    for s in states:
        canvas.state = s
        canvas.repaint()

    # Test muted and speaking states
    canvas.muted = True
    canvas.repaint()
    canvas.muted = False

    canvas.speaking = True
    canvas.repaint()
    canvas.speaking = False

    canvas.close()
