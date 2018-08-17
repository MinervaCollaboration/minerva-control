from pywinauto import application
import ipdb

# a total hack to home the telescope through the GUI...

# attach to PWI GUI
app = application.Application().connect_(title_re = ".*PWI*")
pwi = app.window_(title_re = ".*PWI*")

ipdb.set_trace()

# Select Mount tab
pwi.Dialog.TabControl.Select(2)


pwi.TypeKeys("%H A")

ipdb.set_trace()
