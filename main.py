"""
TODO:

- Line clear animation [mostly done, drop animation is buggy]
- full bonus scoring logic
- hard drop animation [DONE]
- reset lock timer on successful rotate [half-done (need second timer)]
- random piece selection logic [DONE]
- DAS [DONE]
- Wall kicks [DONE]
- Sounds [DONE]
- fix bug where hard drops don't "settle" immediately [DONE]
- level timing [DONE]
- Game menus etc.
- controller input
- 2 player???
- loading screen?
- Non-copyrighted assets (lol)
"""

from enum import Enum, auto
from abc import ABC, abstractmethod
import random
import pygame

from data import CENTRE_SHIFT, SHAPES, WALLKICKS

BLACK = (0x00, 0x00, 0x00)
WHITE = (0xff, 0xff, 0xff)

pygame.init()
pygame.font.init()
pygame.mixer.init()

font = pygame.font.Font("./assets/fonts/CenturyGothic.ttf", 20)
mediumfont = pygame.font.SysFont("Ubuntu", 48)
hugefont = pygame.font.SysFont("Ubuntu", 128)

size = width, height = 1280, 720
render_surface = pygame.surface.Surface(size)
screen = pygame.display.set_mode((width*2, height*2))

clock = pygame.time.Clock()

gridwidth, gridheight = 10, 24
topzone = 4
cell_size = 26 #(height * 0.8) // (gridheight - topzone)

top_margin = (height - (cell_size*(gridheight-topzone))) // 2
left_margin = (width - (cell_size*gridwidth)) // 2

CLEAR_ANIMATION_DELAY = 20 # frames
CLEAR_ANIMATION_DURATION = 5 # frames

sfx = {
	"move":        pygame.mixer.Sound("assets/sound/move.wav"),
	"rotate":      pygame.mixer.Sound("assets/sound/rotate.wav"),
	"hardDrop":    pygame.mixer.Sound("assets/sound/hardDrop.wav"),
	"tetris":      pygame.mixer.Sound("assets/sound/tetris.wav"),
	"lineClear":   pygame.mixer.Sound("assets/sound/lineClear.wav"),
	"collapse":    pygame.mixer.Sound("assets/sound/collapse.wav"),
	"blockout":    pygame.mixer.Sound("assets/sound/blockout.wav"),
	"levelUp":     pygame.mixer.Sound("assets/sound/levelUp.wav"),
	"lock":        pygame.mixer.Sound("assets/sound/lock.wav"),
	"hold":        pygame.mixer.Sound("assets/sound/hold.wav"),
	"korobeiniki": pygame.mixer.Sound("assets/sound/Korobeiniki-F01.wav")
}

pygame.mixer.music.load("assets/sound/Korobeiniki-F01.wav")

def load_images():
	images = {}
	for mode in ["dying", "ghost", "locked", "normal"]:
		images[mode] = {}
		for shape in "IJLOSTZ":
			images[mode][shape] = pygame.image.load(f"assets/images/mino-01-{mode}-~size-25~-{shape}.png")
	return images

imgs = load_images()
bgimg = pygame.image.load("assets/images/main-background.png")
matriximg = pygame.image.load("assets/images/matrix.png")
vfx_harddrop = pygame.image.load("assets/images/vfx-hardDrop.png")
vfx_sparkle = pygame.image.load("assets/images/vfx-sparkle.png")
vfx_minolocked = pygame.image.load("assets/images/vfx-minoLocked-01.png")

# pre-bake sprite frames for the line clear animation
minolock_frames = []
scale = 1.0
for i in range(26):
	if i <= 5:
		scale += 0.05
	else:
		scale -= 0.05
	frame = pygame.transform.rotozoom(vfx_minolocked, -i*5, scale)
	frame.set_alpha(200 * (1 - i/26))
	minolock_frames.append(frame)

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
		self.sprite = pygame.transform.smoothscale(vfx_harddrop, (26, 26*height))
	
	def update(self):
		self.alpha -= 5
		return self.alpha > 0
	
	def render(self, surface):
		self.sprite.set_alpha(self.alpha)
		surface.blit(self.sprite, (left_margin + self.col * cell_size, top_margin + self.row * cell_size))


class SparkleParticle(Particle):
	def __init__(self, row, col, alpha):
		self.row = row + random.random()
		self.col = col + random.random()
		self.yvel = 0.01 + random.random() * 0.01
		self.alpha = alpha
		sparkle_size = 3 + random.random() * 4
		self.sprite = pygame.transform.smoothscale(vfx_sparkle, (sparkle_size, sparkle_size))
	
	def update(self):
		self.alpha -= 5
		self.row -= self.yvel
		return self.alpha > 0
	
	def render(self, surface):
		self.sprite.set_alpha(self.alpha)
		surface.blit(self.sprite, (
			int(left_margin + self.col * cell_size),
			int(top_margin + self.row * cell_size)
		))


class RowClearParticle(Particle):
	def __init__(self, row, col, anim_progress):
		self.row = row
		self.col = col
		self.anim_progress = anim_progress
	
	def update(self):
		self.anim_progress += 1
		return self.anim_progress < 26
	
	def render(self, surface):
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
			pygame.mixer.music.stop()

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
		if linecount == 4:
			sfx["tetris"].play()
		else:
			sfx["lineClear"].play()
		sfx["collapse"].play()
		
		self.score += self.level * [0, 100, 300, 500, 800][linecount]
		new_line_total = self.line_count + linecount
		if self.line_count // 10 != new_line_total // 10: # if we crossed a new multiple of 10 boundary
			self.level += 1
			sfx["levelUp"].play()
		self.line_count = new_line_total

		self.line_clear_animation_ticks_remaining = CLEAR_ANIMATION_DELAY + CLEAR_ANIMATION_DURATION

		return True
		
	def pause(self):
		self.gamestate = GameState.PAUSED
		pygame.mixer.music.pause()
	
	def unpause(self):
		self.gamestate = GameState.PLAYING
		pygame.mixer.music.unpause()

	def update(self, events):
		if self.gamestate == GameState.PLAYING:
			self.update_gameloop(events)
		elif self.gamestate == GameState.PAUSED:
			for event in events:
				if event.type == pygame.KEYDOWN and event.key == pygame.K_p:
					self.unpause()
		elif self.gamestate == GameState.GAMEOVER:
			for event in events:
				if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
					self.__init__()
	
	def update_gameloop(self, events):
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
			if event.type == pygame.KEYDOWN:
				if event.key in [pygame.K_UP, pygame.K_x]:
					self.try_rotate(1)
				#if event.key == pygame.K_DOWN:
				#    if self.try_movey(1):
				#        self.score += 1
				#if event.key == pygame.K_LEFT:
				#    self.try_movex(-1)
				#if event.key == pygame.K_RIGHT:
				#    self.try_movex(1)
				if event.key == pygame.K_z:
					self.try_rotate(-1)
				if event.key == pygame.K_c:
					self.swap_hold()
				if event.key == pygame.K_SPACE:
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
					self.lockdown()
				
				if event.key == pygame.K_p:
					self.pause()
		
		# keep track of how long these keys have been held
		keys = pygame.key.get_pressed()
		if keys[pygame.K_DOWN]:
			self.heldticks["down"] += 1
		else:
			self.heldticks["down"] = 0
		if keys[pygame.K_LEFT]:
			self.heldticks["left"] += 1
		else:
			self.heldticks["left"] = 0
		if keys[pygame.K_RIGHT]:
			self.heldticks["right"] += 1
		else:
			self.heldticks["right"] = 0
		
		if self.heldticks["down"] == 1: # sfx on first press
			sfx["move"].play()
		if self.heldticks["down"] % 2 == 1: # 30Hz softdrop
			if self.try_movey(1):
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

	def render(self, surface):
		self.render_gameplay(surface)
		
		if self.gamestate == GameState.PAUSED:
			self.render_message_overlay(surface, "PAUSED", "Press P to resume")
		elif self.gamestate == GameState.GAMEOVER:
			self.render_message_overlay(surface, "GAME OVER", f"Score: {self.score:,}")

	def render_message_overlay(self, surface, text_string, subtitle=""):
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

	def render_gameplay(self, surface):
		surface.blit(bgimg, (240, 61))
		surface.blit(matriximg, (240+264, 61+32))

		# draw particles (under everything else)
		for particle in self.particles:
			particle.render(surface)

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
					surface.blit(imgs["locked"][cell], (left_margin + x * cell_size, top_margin + (y + (slide if y < slide_thresh else 0)) * cell_size))

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
						surface.blit(imgs["ghost"][val], (left_margin + posx * cell_size, top_margin + posy * cell_size))

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
						imgs["normal"][val].set_alpha(alpha)
						surface.blit(imgs["normal"][val], (left_margin + posx * cell_size, top_margin + posy * cell_size))
						imgs["normal"][val].set_alpha(255)

		# draw preview of next shape
		for i, shape in enumerate(self.shape_queue):
			shape_sprite = SHAPES[shape][0]
			shift = CENTRE_SHIFT[shape]
			for y, row in enumerate(shape_sprite):
				for x, val in enumerate(row):
					if val != " ":
						surface.blit(imgs["normal"][val], (left_margin + (x + gridwidth + 3 + shift) * cell_size, top_margin - 4 + (y + 3 + i * 2.5) * cell_size))

		# draw hold
		if self.hold:
			shape_sprite = SHAPES[self.hold][0]
			shift = CENTRE_SHIFT[self.hold]
			for y, row in enumerate(shape_sprite):
				for x, val in enumerate(row):
					if val != " ":
						surface.blit(imgs["normal"][val], (left_margin + 4 + (x - 7 + shift) * cell_size, top_margin - 4 + (y + 3) * cell_size))


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


def main():
	"""
		Main loop happens here
	"""

	state = Game()

	frametime = 0
	while True:
		frame_start = pygame.time.get_ticks()

		events = pygame.event.get()

		for event in events:
			if event.type == pygame.QUIT:
				return # exit
			if event.type == pygame.ACTIVEEVENT and event.state == 1 and event.gain == 0:
				if state.gamestate != GameState.GAMEOVER:
					state.pause()

		state.update(events)

		# render game state
		render_surface.fill((0, 0, 0))
		state.render(render_surface)
		scaled = pygame.transform.scale2x(render_surface)
		screen.blit(scaled, (0, 0))

		# show time it took to render the previous frame (we have a 16ms time budget to hit 60fps)
		screen.blit(font.render(f"{frametime:.2f}ms", True, WHITE), (10, 10))

		pygame.display.flip()

		frametime = pygame.time.get_ticks() - frame_start

		# wait for the next 60Hz interval
		clock.tick(60)

if __name__ == "__main__":
	main()
