import os

# asahi linux things
if "asahi" in os.uname().release:
	print("INFO: applying asahi linux gl config hack")
	os.environ["MESA_GL_VERSION_OVERRIDE"] = "3.3"
	os.environ["MESA_GLSL_VERSION_OVERRIDE"] = "330"
	os.environ["MESA_GLES_VERSION_OVERRIDE"] = "3.1"

from enum import Enum, auto
from abc import ABC, abstractmethod
import random
import pyglet
from pyglet.window import key
#from pyglet import gl
#gl.glEnable(gl.GL_BLEND)
#gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

from data import CENTRE_SHIFT, SHAPES, WALLKICKS



size = width, height = 800, 600
window = pyglet.window.Window(width, height)
keys = key.KeyStateHandler()
#window.push_handlers(keys)

fps_display = pyglet.window.FPSDisplay(window=window)

gridwidth, gridheight = 10, 24
topzone = 4
cell_size = 26 #(height * 0.8) // (gridheight - topzone)

top_margin = (height - (cell_size*(gridheight-topzone-2))) // 2
left_margin = (width - (cell_size*gridwidth)) // 2

CLEAR_ANIMATION_DELAY = 20 # frames
CLEAR_ANIMATION_DURATION = 5 # frames

sfx = {
	"move":        pyglet.resource.media("assets/sound/move.wav", streaming=False),
	"rotate":      pyglet.resource.media("assets/sound/rotate.wav", streaming=False),
	"hardDrop":    pyglet.resource.media("assets/sound/hardDrop.wav", streaming=False),
	"tetris":      pyglet.resource.media("assets/sound/tetris.wav", streaming=False),
	"lineClear":   pyglet.resource.media("assets/sound/lineClear.wav", streaming=False),
	"collapse":    pyglet.resource.media("assets/sound/collapse.wav", streaming=False),
	"blockout":    pyglet.resource.media("assets/sound/blockout.wav", streaming=False),
	"levelUp":     pyglet.resource.media("assets/sound/levelUp.wav", streaming=False),
	"lock":        pyglet.resource.media("assets/sound/lock.wav", streaming=False),
	"hold":        pyglet.resource.media("assets/sound/hold.wav", streaming=False),
	"korobeiniki": pyglet.resource.media("assets/sound/Korobeiniki-F01.wav")
}

bgm = sfx["korobeiniki"]
# TODO: play in loop

def load_images():
	images = {}
	for mode in ["dying", "ghost", "locked", "normal"]:
		images[mode] = {}
		for shape in "IJLOSTZ":
			images[mode][shape] = pyglet.resource.image(f"assets/images/mino-01-{mode}-~size-25~-{shape}.png")
	return images

imgs = load_images()
bgimg = pyglet.resource.image("assets/images/main-background.png")
matriximg = pyglet.resource.image("assets/images/matrix.png")
vfx_harddrop = pyglet.resource.image("assets/images/vfx-hardDrop.png")
vfx_sparkle = pyglet.resource.image("assets/images/vfx-sparkle.png")
vfx_minolocked = pyglet.resource.image("assets/images/vfx-minoLocked-01.png")
vfx_minolocked.anchor_x = vfx_minolocked.width / 2
vfx_minolocked.anchor_y = vfx_minolocked.height / 2


minolock_frames = [] # (rotation, scale, alpha)
scale = 1.0
for i in range(26):
	if i <= 5:
		scale += 0.05
	else:
		scale -= 0.05
	minolock_frames.append((i*5, scale, 200 * (1 - i/26)))


class Particle(ABC):
	@abstractmethod
	def update(self):
		"""
		Returns True if the particle is still alive, False if its dead
		"""
		pass

	@abstractmethod
	def render(self, surface):
		pass

class StreakParticle(Particle):
	def __init__(self, row, col, height):
		"""
		row is the top row, "height" extends downwards (positive direction)
		"""
		self.alpha = 128
		self.row = row
		self.col = col
		self.height = height
		#self.sprite = pygame.transform.smoothscale(vfx_harddrop, (26, 26*height))
	
	def update(self):
		self.alpha -= 5
		return self.alpha > 0
	
	def render(self, batch):
		self.sprite = pyglet.sprite.Sprite(
			vfx_harddrop,
			left_margin + self.col * cell_size,
			height - (top_margin + (self.row + self.height) * cell_size),
			batch=batch)
		self.sprite.opacity = self.alpha
		self.sprite.scale_y = self.height

class SparkleParticle(Particle):
	def __init__(self, row, col, alpha):
		self.row = row + random.random()
		self.col = col + random.random()
		self.yvel = 0.01 + random.random() * 0.01
		self.alpha = alpha
		self.scale = (3 + random.random() * 4) / 32
		#self.sprite = pygame.transform.smoothscale(vfx_sparkle, (sparkle_size, sparkle_size))
	
	def update(self):
		self.alpha -= 5
		self.row -= self.yvel
		return self.alpha > 0
	
	def render(self, batch):
		self.sprite = pyglet.sprite.Sprite(
			vfx_sparkle,
			int(left_margin + self.col * cell_size),
			height - int(top_margin + self.row * cell_size),
			batch=batch
		)
		self.sprite.opacity = self.alpha
		self.sprite.scale = self.scale


class RowClearParticle(Particle):
	def __init__(self, row, col, anim_progress):
		self.row = row
		self.col = col
		self.anim_progress = anim_progress
	
	def update(self):
		self.anim_progress += 1
		return self.anim_progress < 26
	
	def render(self, batch):
		rotation, scale, alpha = minolock_frames[max(0, int(self.anim_progress))]
		self.sprite = pyglet.sprite.Sprite(
			vfx_minolocked,
			left_margin + (self.col + 0.5 ) * cell_size,
			height - (top_margin + (self.row - 0.5) * cell_size),
			batch=batch
		)
		self.sprite.rotation = -rotation
		self.sprite.scale = scale
		self.sprite.opacity = alpha
		return
		#vfx_minolocked.set_alpha((1 - max(0, self.anim_progress)/20) * 255)
		sprite = minolock_frames[max(0, int(self.anim_progress))]
		#sprite.set_alpha(80)
		#assert(type(sprite) is pygame.Surface)
		w, h = sprite.get_size()
		surface.blit(sprite, (
			left_margin + (self.col + 0.5 ) * cell_size - w / 2,
			top_margin + (self.row + 0.5) * cell_size - h / 2
		))

class GameState(Enum):
	"""
		all possible gameplay states
	"""
	PLAYING = auto()
	PAUSED = auto()
	ANIMATING = auto()  # game logic paused for rendering line-clear animation
	GAMEOVER = auto()

class Game:
	"""
		Contains the entire game state, gameplay logic, and rendering logic
	"""

	def __init__(self):
		self.random_bag = []
		self.gamestate = GameState.PLAYING
		self.gridstate = [[" "]*gridwidth for _ in range(gridheight)]
		self.shape_queue = [self.random_shape() for _ in range(3)]
		self.score = 0
		self.level = 1
		self.line_count = 0
		self.gameticks = 0
		self.time_til_drop = self.time_per_drop()
		self.line_clear_animation_ticks_remaining = 0
		self.rows_to_collapse = []
		self.prev_back2back = False
		self.prevkeys = dict()
		self.heldticks = {
			"left": 0,
			"right": 0,
			"down": 0
		}
		self.hold = None
		self.can_swap = True

		self.active_shape = None
		self.active_x = None
		self.active_y = None
		self.active_rot = None
		self.particles = []
		self.spawn_shape()

		#pygame.mixer.music.play(-1, 0.0)
	
	def random_shape(self):
		if not self.random_bag:
			self.random_bag = list(SHAPES.keys())
			random.shuffle(self.random_bag)
		return self.random_bag.pop()

	def spawn_shape(self, respawn=False):
		if not respawn:
			self.active_shape = self.shape_queue.pop(0)
			self.shape_queue.append(self.random_shape())
		self.active_x = 3
		self.active_y = 2
		self.active_rot = 0

		if self.does_collide():
			self.gamestate = GameState.GAMEOVER
			sfx["blockout"].play()
			#pygame.mixer.music.stop()

	def try_rotate(self, direction):
		new_rot = (self.active_rot + direction) % 4
		wallkicks = WALLKICKS[self.active_shape][(self.active_rot, new_rot)]

		for dx, dy in wallkicks:
			new_x = self.active_x + dx
			new_y = self.active_y - dy  # positive Y is upwards, in wallkick data (because that's what the tetris wiki uses)
			if not self.does_collide(new_x, new_y, new_rot):
				self.active_rot = new_rot
				self.active_x = new_x
				self.active_y = new_y
				sfx["rotate"].play()
				if self.is_resting(): #XXX should this be if it *was* resting?
					self.time_til_drop = self.time_per_drop()
				return True
		
		return False
	
	def try_movex(self, direction):
		self.active_x += direction
		if self.does_collide():
			# revert
			self.active_x -= direction
			return False
		else:
			sfx["move"].play()
			if self.is_resting():
				self.time_til_drop = self.time_per_drop()
			return True
	
	def try_movey(self, direction):
		self.active_y += direction
		if self.does_collide():
			# revert
			self.active_y -= direction
			return False
		else:
			return True

	def stamp_piece(self):
		shape_sprite = SHAPES[self.active_shape][self.active_rot]
		for y, row in enumerate(shape_sprite):
			for x, val in enumerate(row):
				posy = self.active_y + y
				posx = self.active_x + x
				if val != " ":
					self.gridstate[posy][posx] = val

	def is_resting(self):
		return self.does_collide(testy=self.active_y+1)

	def does_collide(self, testx=None, testy=None, testrot=None):
		if testx is None:
			testx = self.active_x
		if testy is None:
			testy = self.active_y
		if testrot is None:
			testrot = self.active_rot

		shape_sprite = SHAPES[self.active_shape][testrot]
		for y, row in enumerate(shape_sprite):
			for x, val in enumerate(row):
				posy = testy + y
				posx = testx + x
				if posy >= gridheight:
					if val != " ":
						return True  # we hit the floor
					continue  # an empty cell within the bounding box is through the floor, ignore
				if posx < 0 or posx >= gridwidth:
					if val != " ":
						return True  # we hit a wall
					continue  # an empty cell within bounding box is outside the walls, ignore
				if posy < 0:
					continue  # I don't think this should ever happen, but if we're above the ceiling, ignore
				
				# if we reached here, (posx, posy) is definitely inside the grid
				if val != " " and self.gridstate[posy][posx] != " ":
					return True  # collision with a block already on the grid
		
		# if we made it this far, there were no collisions
		return False
	
	def do_collapse_rows(self):
		for y in range(gridheight):  # scan the grid from top to bottom
			if y in self.rows_to_collapse:
				self.gridstate = [[" "] * gridwidth] + self.gridstate[:y] + self.gridstate[y+1:]
		self.rows_to_collapse = []

	def check_lines(self):
		self.rows_to_collapse = []
		for y in range(gridheight):  # scan the grid from top to bottom
			if self.gridstate[y].count(" ") == 0:
				self.gridstate[y] = [" "] * gridwidth
				for x in range(gridwidth):
					self.particles.append(RowClearParticle(
						y - topzone, x, -x
					))
				self.rows_to_collapse.append(y)
		
		if not self.rows_to_collapse:
			return False
		
		linecount = len(self.rows_to_collapse)
		back2back_bonus = 1.0
		if linecount == 4:
			if self.prev_back2back:
				back2back_bonus = 1.5
			sfx["tetris"].play()
			self.prev_back2back = True
		else:
			sfx["lineClear"].play()
			self.prev_back2back = False
		sfx["collapse"].play()
		
		self.score += int(self.level * [0, 100, 300, 500, 800][linecount] * back2back_bonus)
		new_line_total = self.line_count + linecount
		if self.line_count // 10 != new_line_total // 10: # if we crossed a new multiple of 10 boundary
			self.level += 1
			sfx["levelUp"].play()
		self.line_count = new_line_total

		self.line_clear_animation_ticks_remaining = CLEAR_ANIMATION_DELAY + CLEAR_ANIMATION_DURATION

		return True
		
	def pause(self):
		self.gamestate = GameState.PAUSED
		#pygame.mixer.music.pause()
	
	def unpause(self):
		self.gamestate = GameState.PLAYING
		#pygame.mixer.music.unpause()

	def update(self, dt, keys, events):

		if self.gamestate == GameState.PLAYING:
			self.update_gameloop(dt, keys, events)
		elif self.gamestate == GameState.PAUSED:
			for event in events:
				if event == key.P:
					self.unpause()
		elif self.gamestate == GameState.GAMEOVER:
			for event in events:
				if event == key.RETURN:
					self.__init__()
		
		events.clear()
	
	def update_gameloop(self, dt, keys, events):
		# update particles (keep only those that are still alive!)
		self.particles = list(filter(lambda p: p.update(), self.particles))

		if self.line_clear_animation_ticks_remaining > 0:
			self.line_clear_animation_ticks_remaining -= 1
			if self.line_clear_animation_ticks_remaining == 0:
				self.do_collapse_rows()
				self.spawn_shape()
			return

		self.gameticks += 1

		for event in events:
			if event in [key.UP, key.X]:
				self.try_rotate(1)
			#if event.key == pygame.K_DOWN:
			#    if self.try_movey(1):
			#        self.score += 1
			#if event.key == pygame.K_LEFT:
			#    self.try_movex(-1)
			#if event.key == pygame.K_RIGHT:
			#    self.try_movex(1)
			if event == key.Z:
				self.try_rotate(-1)
			if event == key.C:
				self.swap_hold()
			if event == key.SPACE:
				drop_top = self.active_y

				while self.try_movey(1):
					self.score += 2
				
				drop_height = self.active_y - drop_top
				visited_cols = set()
				shape_sprite = SHAPES[self.active_shape][self.active_rot]
				for y, row in list(enumerate(shape_sprite))[::-1]:
					for x, val in enumerate(row):
						if val != " ":
							if x in visited_cols:
								continue
							visited_cols.add(x)

							self.particles.append(StreakParticle(
								drop_top + y - topzone,
								self.active_x + x,
								drop_height
							))

							for sparkle_y in range(drop_height):
								if random.random() > 0.5:
									continue
								self.particles.append(SparkleParticle(
									drop_top + y - topzone + sparkle_y,
									self.active_x + x,
									(sparkle_y/drop_height) * 200
								))
				sfx["hardDrop"].play()
				self.time_til_drop = self.time_per_drop()
				self.lockdown()
			
			if event == key.P:
				self.pause()
		
		# keep track of how long these keys have been held
		if keys[key.DOWN]:
			self.heldticks["down"] += 1
		else:
			self.heldticks["down"] = 0
		if keys[key.LEFT]:
			self.heldticks["left"] += 1
		else:
			self.heldticks["left"] = 0
		if keys[key.RIGHT]:
			self.heldticks["right"] += 1
		else:
			self.heldticks["right"] = 0
		
		if self.heldticks["down"] == 1: # sfx on first press
			sfx["move"].play()
		if self.heldticks["down"] % 2 == 1: # 30Hz softdrop
			if self.try_movey(1):
				self.time_til_drop = self.time_per_drop()
				self.score += 1
		
		if self.heldticks["left"] == 1 or (self.heldticks["left"] > 10 and self.heldticks["left"] % 2 == 1):  # 30Hz ARR, 10 frame DAS
			self.try_movex(-1)
		
		if self.heldticks["right"] == 1 or (self.heldticks["right"] > 10 and self.heldticks["right"] % 2 == 1):  # 30Hz ARR, 10 frame DAS
			self.try_movex(1)
		
		self.time_til_drop -= 1/60
		if self.time_til_drop < 0:
			self.apply_gravity()
			self.time_til_drop += self.time_per_drop()
	
	def time_per_drop(self):
		return (0.8 - ((self.level - 1) * 0.007)) ** (self.level - 1)

	def swap_hold(self):
		if not self.can_swap:
			return
		sfx["hold"].play()

		if self.hold is None:
			self.hold = self.active_shape
			self.spawn_shape()
		else:
			self.active_shape, self.hold = self.hold, self.active_shape
			self.spawn_shape(respawn=True)
		
		self.can_swap = False # this gets reset on next lockdown
	
	def lockdown(self):
		self.stamp_piece()
		if not self.check_lines():
			self.spawn_shape()
		self.can_swap = True
		sfx["lock"].play()
	
	def apply_gravity(self):
		if not self.try_movey(1):
			#print(self.last_rotate_tick, self.last_drop_time * 60)
			#if self.last_rotate_tick + 60 < self.last_drop_time * 60:
			self.lockdown()


	# ======== RENDERING LOGIC ========

	def render(self, window):
		self.render_gameplay(window)
		
		if self.gamestate == GameState.PAUSED:
			self.render_message_overlay(window, "PAUSED", "Press P to resume")
		elif self.gamestate == GameState.GAMEOVER:
			self.render_message_overlay(window, "GAME OVER", f"Score: {self.score:,}")

	def render_message_overlay(self, window, text_string, subtitle=""):
		return
		overlay = pygame.Surface(size)
		overlay.set_alpha(128)
		overlay.fill(BLACK)
		surface.blit(overlay, (0, 0))
		
		# render centered text
		text = hugefont.render(text_string, True, WHITE)
		text_rect = text.get_rect(center=(width//2, height//3))
		surface.blit(text, text_rect)

		text = mediumfont.render(subtitle, True, WHITE)
		text_rect = text.get_rect(center=(width//2, height//2))
		surface.blit(text, text_rect)

	def render_gameplay(self, window):
		batch = pyglet.graphics.Batch()
		#background = pyglet.graphics.Group(order=0)
		#foreground = pyglet.graphics.Group(order=1)
		self.sprites = []
		self.sprites.append(pyglet.sprite.Sprite(bgimg, batch=batch))
		self.sprites.append(pyglet.sprite.Sprite(matriximg, 264, 32, batch=batch))

		# draw particles (under everything else)
		for particle in self.particles:
			particle.render(batch)

		# draw main grid state
		if self.rows_to_collapse and 0 < self.line_clear_animation_ticks_remaining < CLEAR_ANIMATION_DURATION:
			slide_thresh = min(self.rows_to_collapse) - topzone
			slide = 1 + max(self.rows_to_collapse) - min(self.rows_to_collapse)
			slide *= 1 - (self.line_clear_animation_ticks_remaining / CLEAR_ANIMATION_DURATION)
		else:
			slide = 0
			slide_thresh = 0
		for y in range(gridheight - topzone):
			for x in range(gridwidth):
				cell = self.gridstate[y+topzone][x]
				if cell != " ":
					self.sprites.append(pyglet.sprite.Sprite(imgs["locked"][cell],
						left_margin + x * cell_size,
						height - (top_margin + (y + (slide if y < slide_thresh else 0)) * cell_size),
						batch=batch
					))

		# find ghost position
		for ghosty in range(self.active_y, gridheight):
			if self.does_collide(testy=(ghosty + 1)):
				break
		
		# draw ghost
		if not self.line_clear_animation_ticks_remaining:
			shape_sprite = SHAPES[self.active_shape][self.active_rot]
			for y, row in enumerate(shape_sprite):
				posy = ghosty + y - topzone
				if posy < 0:
					continue
				for x, val in enumerate(row):
					if val != " ":
						posx = self.active_x+x
						self.sprites.append(pyglet.sprite.Sprite(imgs["ghost"][val],
							left_margin + posx * cell_size, 
							height - (top_margin + posy * cell_size),
							batch=batch
						))

		# draw active shape
		if not self.line_clear_animation_ticks_remaining:
			if self.is_resting():
				alpha = int((self.time_til_drop / self.time_per_drop()) * 255)
			else:
				alpha = 255
			shape_sprite = SHAPES[self.active_shape][self.active_rot]
			for y, row in enumerate(shape_sprite):
				posy = self.active_y + y - topzone
				if posy < 0:
					continue
				for x, val in enumerate(row):
					if val != " ":
						posx = self.active_x + x
						#imgs["normal"][val].set_alpha(alpha)
						s = pyglet.sprite.Sprite(
							imgs["normal"][val],
							left_margin + posx * cell_size,
							height - (top_margin + posy * cell_size),
							batch=batch
						)
						s.opacity = alpha
						self.sprites.append(s)
						#imgs["normal"][val].set_alpha(255)

		# draw preview of next shape
		for i, shape in enumerate(self.shape_queue):
			shape_sprite = SHAPES[shape][0]
			shift = CENTRE_SHIFT[shape]
			for y, row in enumerate(shape_sprite):
				for x, val in enumerate(row):
					if val != " ":
						self.sprites.append(pyglet.sprite.Sprite(
							imgs["normal"][val],
							left_margin + (x + gridwidth + 3 + shift) * cell_size,
							height - (top_margin - 4 + (y + 3 + i * 2.5) * cell_size),
							batch=batch
						))

		# draw hold
		if self.hold:
			shape_sprite = SHAPES[self.hold][0]
			shift = CENTRE_SHIFT[self.hold]
			for y, row in enumerate(shape_sprite):
				for x, val in enumerate(row):
					if val != " ":
						self.sprites.append(pyglet.sprite.Sprite(
							imgs["normal"][val],
							left_margin + 4 + (x - 7 + shift) * cell_size,
							height - (top_margin - 4 + (y + 3) * cell_size),
							batch=batch
						))

		batch.draw()
		return

		# score
		rendered_score = font.render(f"{self.score:,}", True, WHITE)
		surface.blit(rendered_score, (384-rendered_score.get_width()//2, 440))

		rendered_level = font.render(f"{self.level}", True, WHITE)
		surface.blit(rendered_level, (384-rendered_level.get_width()//2, 500))

		rendered_line_count = font.render(f"{self.line_count}", True, WHITE)
		surface.blit(rendered_line_count, (384-rendered_line_count.get_width()//2, 560))


		# "particle" effects

		#scaled_vfx = pygame.transform.smoothscale(vfx_harddrop, (26*3, 26*10))
		#surface.blit(scaled_vfx, (600, 400))



game = Game()

keysdown = set()

pyglet.clock.schedule_interval(lambda dt: game.update(dt, keys, keysdown), 1/60.0)

@window.event
def on_key_press(symbol, modifiers):
	keysdown.add(symbol)

@window.event
def on_draw():
	window.clear()
	game.render(window)
	fps_display.draw()

window.push_handlers(keys)
pyglet.app.run()
