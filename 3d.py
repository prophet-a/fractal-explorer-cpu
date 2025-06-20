from ursina import *
from ursina.shaders import lit_with_shadows_shader
from ursina.prefabs.editor_camera import EditorCamera
import math

app = Ursina()
window.color = color.rgb(0,0,10)

# Камера для обертання і зума
EditorCamera(rotation=(20,30,0), rotation_smoothing=2, zoom_speed=2)

# Світло і тіні
DirectionalLight(rotation=(45,-45,45), shadows=True)
AmbientLight(color=color.rgb(50,50,60))

# Mesh setup
mesh = Mesh(vertices=[], triangles=[])
obj = Entity(model=mesh, shader=lit_with_shadows_shader, color=color.white)

MAX_VERTS = 100
current_N = 4
prev_shape, target_shape = [], []
anim_t = 1  # для плавності морфа

# Генеруємо форми
def generate_shape(N):
    verts = []
    if N == 3:  # Тетраедр
        h = math.sqrt(2)/2
        verts = [Vec3(-0.5,0,-0.288), Vec3(0.5,0,-0.288), Vec3(0,h,-0.288), Vec3(0,0,0.866)]
    elif N == 4:  # Піраміда
        verts = [Vec3(-0.5,-0.5,0),Vec3(0.5,-0.5,0),Vec3(0.5,0.5,0),Vec3(-0.5,0.5,0),Vec3(0,0,1)]
    elif N == 6:  # Куб
        verts = [Vec3(x,y,z) for x in (-.5,.5) for y in (-.5,.5) for z in (-.5,.5)]
    else:  # Призма з N-кутною основою
        h = 0.5
        for z in (-h,h):
            for i in range(N):
                angle = 2*math.pi*i/N
                verts.append(Vec3(math.cos(angle)*0.5, math.sin(angle)*0.5, z))
    # Додаємо пусті вершини, якщо їх менше MAX_VERTS
    while len(verts) < MAX_VERTS:
        verts.append(Vec3(0,0,0))
    return verts[:MAX_VERTS]

def morph_to(N):
    global current_N, prev_shape, target_shape, anim_t
    prev_shape = [v for v in obj.model.vertices]
    target_shape = generate_shape(N)
    current_N = N
    anim_t = 0

def update():
    global anim_t
    if anim_t < 1:
        anim_t += time.dt
        anim_t = min(anim_t,1)
        # Лінійна інтерполяція вершин
        for i in range(MAX_VERTS):
            mesh.vertices[i] = lerp(prev_shape[i], target_shape[i], anim_t)
        mesh.generate()

# Стартова побудова
mesh.vertices = generate_shape(current_N)

# Генеруємо прості трикутники (без фанів, для коректних тіней)
mesh.triangles = [(i,(i+1)%MAX_VERTS,(i+2)%MAX_VERTS) for i in range(MAX_VERTS-2)]
mesh.generate()

# UI
btn_plus  = Button('+', scale=0.07, position=window.top_right + Vec2(-0.08,-0.1))
btn_minus = Button('-', scale=0.07, position=window.top_right + Vec2(-0.08,-0.18))
lcd       = Text(str(current_N), scale=2, position=window.top_right + Vec2(-0.085,-0.26))

def change_N(delta):
    global current_N
    newN = clamp(current_N + delta, 3, 20)
    lcd.text = str(newN)
    morph_to(newN)

btn_plus.on_click  = lambda: change_N(+1)
btn_minus.on_click = lambda: change_N(-1)

app.run()
