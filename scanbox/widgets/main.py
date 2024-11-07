from .utils import *

class Scanbox(QMainWindow):
    def __init__(self, config = None, server = None):
        super(Scanbox,self).__init__()
        self.config = config
        if 'server' in self.config.keys():
            self.server = self.config['server']
        else:
            self.server = server
        # set the remote connections server
        self._connect_control_server()
        self.docks = []
        # set up the cameras displays
        self.cams = {}
        self.cam_onep = None
        self.cam_widgets = {}
        self._add_cameras()

        self.excitation_mode = '1p'  # or 2p
        # changes what gets triggered when recording

        if 'neurolabware_box' in self.config.keys():
            self.microscope_controller = None
        
        self.widget_timer = QTimer()
        self.widget_timer.timeout.connect(self.update_widget_timer)
        self.widget_timer.start(0.030)
        self.show()
        
    def update_widget_timer(self):
        for k in self.cam_widgets.keys():
            w = self.cam_widgets[k]
            if hasattr(w,'update'):
                w.update()

    def _connect_control_server(self):
        if not self.server is None:
            print(self.server)
            if 'udp' in self.server['type'].lower():
                import socket
                # start udp control server
                display('Connecting remote {type} server on port {port}'.format(
                    **self.server))
                if not 'timeout' in self.server.keys():
                    self.server['timeout'] = 0.02
                if not 'port' in self.server.keys():
                    self.server['port'] = 7000
                    
                self.server['socket'] = socket.socket(socket.AF_INET, 
                                                      socket.SOCK_DGRAM) # UDP
                self.server['socket'].bind(('0.0.0.0',
                                            self.server['port']))
                self.server['socket'].settimeout(self.server['timeout'])
                
    def _add_cameras(self):
        if 'cameras' in self.config.keys():
            import labcams.cams as cams
            for c in self.config['cameras'].keys():
                pars = dict(self.config['cameras'][c])
                if not 'name' in pars.keys():
                    pars['name'] = c
                # if 'one_photon' in c:
                #     self.cam_onep = cams.Camera(**pars)
                #     cam = self.cam_onep
                # else:
                #     self.cams[c] = cams.Camera(**pars)
                #     cam = self.cams[c]
                try:
                # Attempt to initialize the Basler camera
                    if 'one_photon' in c:
                        self.cam_onep = cams.Camera(**pars)
                        cam = self.cam_onep
                    else:
                        self.cams[c] = cams.Camera(**pars)
                        cam = self.cams[c]
                except Exception as e:
                    print(f"Failed to initialize Basler camera for '{c}': {e}")
                    print("Using mock camera instead for testing.")

                    # Define a mock camera as a fallback
                    class MockCamera:
                        def __init__(self, **kwargs):
                            print("Mock Basler Camera initialized with parameters:", kwargs)
                        
                        def start(self):
                            print("Mock camera started")

                        def get_img(self):
                            import numpy as np
                            return np.zeros((480, 640, 3), dtype=np.uint8)  # Black frame for testing
                    
                    # Substitute the failed camera with the mock
                    cam = MockCamera(**pars)
                    if 'one_photon' in c:
                        self.cam_onep = cam
                    else:
                        self.cams[c] = cam
                cam.start()
                cam.cam.start_trigger.set()
                self.cam_widgets[c] = CameraWidget(cam,parent = self)
                self.cam_widgets[c].setMinimumHeight(300)
                self.docks.append(QDockWidget("Camera: "+str(c), self))
                self.docks[-1].setWidget(self.cam_widgets[c])
                self.docks[-1].setFloating(False)
                self.docks[-1].setAllowedAreas(Qt.LeftDockWidgetArea |
                                               Qt.RightDockWidgetArea |
                                               Qt.BottomDockWidgetArea |
                                               Qt.TopDockWidgetArea)
                self.docks[-1].setFeatures(QDockWidget.DockWidgetMovable |
                                           QDockWidget.DockWidgetFloatable)
                self.addDockWidget(
                    Qt.BottomDockWidgetArea,
                    self.docks[-1])
    
class CameraWidget(QWidget):
    def __init__(self,cam,parent = None):
        super(CameraWidget,self).__init__()
        self.parent = parent
        from vispy.app import use_app
        use_app()
        from vispy import scene

        self.canvas = scene.SceneCanvas(keys = 'interactive')
        from vispy.app.qt import QtSceneCanvas
        #self.canvas = QtSceneCanvas()
        self.view = self.canvas.central_widget.add_view()
        self.view.camera = scene.PanZoomCamera(aspect=1)
        self.view.camera.flip = (0, 1, 0)
        self.view.camera.set_range()
        
        self.img_buffer = cam.cam.get_img()
        self.image = scene.visuals.Image(self.img_buffer,
                                         parent = self.view.scene)
        self.canvas.show()
        GUI_UPDATE()
        self.cam = cam
        self.canvas.size = self.img_buffer.shape[:2][::-1]
        lay = QGridLayout()
        self.setLayout(lay)
        #lay.addWidget(self.canvas,0,0)

    def update(self):
        self.image.set_data(self.cam.get_img().squeeze())
        self.canvas.update()
        GUI_UPDATE()

class NeurolabwareControlWidget(QWidget):
    def __init__(self,parent = None):
        pass
        
