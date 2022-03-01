from .utils import *
from .widgets import *
import shutil

def main():
    from argparse import ArgumentParser, RawDescriptionHelpFormatter
    parser = ArgumentParser(description='scanbox',
                            formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument('-u','--user',
                        metavar='user',
                        type=str,
                        default='default')
    
    opts = parser.parse_args()
    
    prefs = get_config(user = opts.user)

    app = QApplication(sys.argv)
    exp = Scanbox(config = prefs)
    
    sys.exit(app.exec_())
    
