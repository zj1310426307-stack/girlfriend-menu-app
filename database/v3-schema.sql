-- LoveOS V3 PostgreSQL schema snapshot
-- Generated from backend/models.py; Alembic remains the migration authority.
-- Alembic head: 20260817_14
-- Regenerate/check with: python scripts/export_v3_schema.py --check

CREATE TABLE achievements (
	id SERIAL NOT NULL,
	code VARCHAR(80) NOT NULL,
	name VARCHAR(100) NOT NULL,
	description TEXT NOT NULL,
	reward_score INTEGER NOT NULL,
	game_type VARCHAR(50),
	metric VARCHAR(50) NOT NULL,
	threshold INTEGER NOT NULL,
	enabled BOOLEAN NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE admin_accounts (
	id SERIAL NOT NULL,
	username VARCHAR(80) NOT NULL,
	password_hash VARCHAR(255) NOT NULL,
	role VARCHAR(30) NOT NULL,
	is_active BOOLEAN NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	last_login_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id)
);

CREATE TABLE ai_players (
	id SERIAL NOT NULL,
	game_type VARCHAR(50) NOT NULL,
	level VARCHAR(20) NOT NULL,
	name VARCHAR(80) NOT NULL,
	config JSONB NOT NULL,
	enabled BOOLEAN NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_ai_player_game_level UNIQUE (game_type, level)
);

CREATE TABLE customers (
	id VARCHAR(100) NOT NULL,
	token_hash VARCHAR(128) NOT NULL,
	display_name VARCHAR(50) NOT NULL,
	is_active BOOLEAN NOT NULL,
	legacy_customer_id VARCHAR(100),
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	last_seen_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id)
);

CREATE TABLE daily_tasks (
	id SERIAL NOT NULL,
	customer_id VARCHAR(100) NOT NULL,
	title VARCHAR(150) NOT NULL,
	type VARCHAR(50) NOT NULL,
	reward_score INTEGER NOT NULL,
	status VARCHAR(20) NOT NULL,
	date DATE NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	completed_at TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (id),
	CONSTRAINT uq_daily_task_customer_date_type UNIQUE (customer_id, date, type)
);

CREATE TABLE dishes (
	id SERIAL NOT NULL,
	name VARCHAR(100) NOT NULL,
	description TEXT,
	category VARCHAR(50) NOT NULL,
	price FLOAT NOT NULL,
	image_url VARCHAR(500),
	cook_time INTEGER,
	difficulty INTEGER,
	spicy_level INTEGER,
	tags JSONB,
	is_active BOOLEAN NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE game_events (
	id SERIAL NOT NULL,
	type VARCHAR(50) NOT NULL,
	content TEXT NOT NULL,
	score INTEGER NOT NULL,
	enabled BOOLEAN NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE game_memories (
	id SERIAL NOT NULL,
	customer_id VARCHAR(100) NOT NULL,
	game_type VARCHAR(50) NOT NULL,
	event VARCHAR(50) NOT NULL,
	content TEXT NOT NULL,
	related_id INTEGER NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_game_memory_event UNIQUE (customer_id, game_type, event, related_id)
);

CREATE TABLE game_rooms (
	id SERIAL NOT NULL,
	room_code VARCHAR(12) NOT NULL,
	game_type VARCHAR(50) NOT NULL,
	creator VARCHAR(100) NOT NULL,
	status VARCHAR(20) NOT NULL,
	max_players INTEGER NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	finished_at TIMESTAMP WITHOUT TIME ZONE,
	last_activity_at TIMESTAMP WITH TIME ZONE NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE,
	state_version INTEGER NOT NULL,
	owner_instance_id VARCHAR(120),
	lease_expires_at TIMESTAMP WITH TIME ZONE,
	lease_epoch INTEGER NOT NULL,
	abandoned_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id)
);

CREATE TABLE game_statistics (
	id SERIAL NOT NULL,
	player_id VARCHAR(100) NOT NULL,
	game_type VARCHAR(50) NOT NULL,
	total_games INTEGER NOT NULL,
	wins INTEGER NOT NULL,
	losses INTEGER NOT NULL,
	draws INTEGER NOT NULL,
	win_rate FLOAT NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_game_stat_player_type UNIQUE (player_id, game_type)
);

CREATE TABLE games (
	id SERIAL NOT NULL,
	name VARCHAR(50) NOT NULL,
	icon VARCHAR(20) NOT NULL,
	type VARCHAR(50) NOT NULL,
	status VARCHAR(20) NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE love_scores (
	id SERIAL NOT NULL,
	customer_id VARCHAR(100) NOT NULL,
	score INTEGER NOT NULL,
	type VARCHAR(50) NOT NULL,
	description TEXT NOT NULL,
	related_id INTEGER,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_love_score_source UNIQUE (customer_id, type, related_id)
);

CREATE TABLE orders (
	id SERIAL NOT NULL,
	status VARCHAR(20) NOT NULL,
	note TEXT,
	desired_time VARCHAR(50),
	desired_at TIMESTAMP WITH TIME ZONE,
	customer_id VARCHAR(100),
	source_order_id INTEGER,
	idempotency_key VARCHAR(100),
	status_updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(source_order_id) REFERENCES orders (id)
);

CREATE TABLE uploaded_images (
	id VARCHAR(32) NOT NULL,
	content_type VARCHAR(50) NOT NULL,
	content BYTEA NOT NULL,
	size INTEGER NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE users (
	id SERIAL NOT NULL,
	user_code VARCHAR(100) NOT NULL,
	nickname VARCHAR(50) NOT NULL,
	avatar VARCHAR(500) NOT NULL,
	role VARCHAR(20) NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE admin_auth_events (
	id SERIAL NOT NULL,
	admin_id INTEGER,
	username VARCHAR(80) NOT NULL,
	outcome VARCHAR(30) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(admin_id) REFERENCES admin_accounts (id) ON DELETE SET NULL
);

CREATE TABLE chess_games (
	id SERIAL NOT NULL,
	room_id INTEGER NOT NULL,
	round_number INTEGER NOT NULL,
	red_player VARCHAR(100) NOT NULL,
	black_player VARCHAR(100),
	winner VARCHAR(100),
	move_count INTEGER NOT NULL,
	duration INTEGER NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	finished_at TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (id),
	CONSTRAINT uq_chess_game_room_round UNIQUE (room_id, round_number),
	FOREIGN KEY(room_id) REFERENCES game_rooms (id) ON DELETE CASCADE
);

CREATE TABLE couple_dates (
	id SERIAL NOT NULL,
	user_id INTEGER NOT NULL,
	title VARCHAR(100) NOT NULL,
	date DATE NOT NULL,
	repeat_type VARCHAR(20) NOT NULL,
	reminder_days INTEGER NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE couple_memories (
	id SERIAL NOT NULL,
	user_id INTEGER NOT NULL,
	type VARCHAR(50) NOT NULL,
	title VARCHAR(100) NOT NULL,
	content TEXT NOT NULL,
	image_url VARCHAR(500) NOT NULL,
	event_date DATE NOT NULL,
	source_type VARCHAR(50),
	source_id INTEGER,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_couple_memory_source UNIQUE (user_id, source_type, source_id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE customer_sessions (
	id SERIAL NOT NULL,
	customer_id VARCHAR(100) NOT NULL,
	token_hash VARCHAR(128) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	last_seen_at TIMESTAMP WITH TIME ZONE NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	revoked_at TIMESTAMP WITH TIME ZONE,
	rotated_from_id INTEGER,
	device_label VARCHAR(100),
	PRIMARY KEY (id),
	FOREIGN KEY(customer_id) REFERENCES customers (id) ON DELETE CASCADE,
	FOREIGN KEY(rotated_from_id) REFERENCES customer_sessions (id) ON DELETE SET NULL
);

CREATE TABLE favorite_dishes (
	id SERIAL NOT NULL,
	customer_id VARCHAR(100) NOT NULL,
	dish_id INTEGER NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_favorite_customer_dish UNIQUE (customer_id, dish_id),
	FOREIGN KEY(dish_id) REFERENCES dishes (id)
);

CREATE TABLE game_actions (
	id SERIAL NOT NULL,
	room_id INTEGER NOT NULL,
	player_id VARCHAR(100) NOT NULL,
	client_action_id VARCHAR(80) NOT NULL,
	action_type VARCHAR(40) NOT NULL,
	request_hash VARCHAR(64) NOT NULL,
	request_version INTEGER NOT NULL,
	response_version INTEGER NOT NULL,
	response_state JSONB NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_game_action_room_player_client UNIQUE (room_id, player_id, client_action_id),
	FOREIGN KEY(room_id) REFERENCES game_rooms (id) ON DELETE CASCADE
);

CREATE TABLE game_event_logs (
	id SERIAL NOT NULL,
	room_id INTEGER NOT NULL,
	event_id INTEGER NOT NULL,
	player_id VARCHAR(100) NOT NULL,
	content TEXT NOT NULL,
	score INTEGER NOT NULL,
	status VARCHAR(20) NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	completed_at TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(room_id) REFERENCES game_rooms (id) ON DELETE CASCADE,
	FOREIGN KEY(event_id) REFERENCES game_events (id)
);

CREATE TABLE game_players (
	id SERIAL NOT NULL,
	room_id INTEGER NOT NULL,
	player_id VARCHAR(100) NOT NULL,
	seat INTEGER NOT NULL,
	score INTEGER NOT NULL,
	joined_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	room_session_token_hash VARCHAR(128),
	last_activity_at TIMESTAMP WITH TIME ZONE NOT NULL,
	disconnected_at TIMESTAMP WITH TIME ZONE,
	expires_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	CONSTRAINT uq_game_player_room_player UNIQUE (room_id, player_id),
	CONSTRAINT uq_game_player_room_seat UNIQUE (room_id, seat),
	FOREIGN KEY(room_id) REFERENCES game_rooms (id) ON DELETE CASCADE
);

CREATE TABLE game_reconnect_tokens (
	id SERIAL NOT NULL,
	room_id INTEGER NOT NULL,
	user_id INTEGER NOT NULL,
	token_hash VARCHAR(64) NOT NULL,
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	revoked BOOLEAN NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_reconnect_room_user UNIQUE (room_id, user_id),
	FOREIGN KEY(room_id) REFERENCES game_rooms (id) ON DELETE CASCADE,
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE game_records (
	id SERIAL NOT NULL,
	room_id INTEGER NOT NULL,
	round_number INTEGER NOT NULL,
	game_type VARCHAR(50) NOT NULL,
	winner VARCHAR(100),
	duration INTEGER NOT NULL,
	result JSONB NOT NULL,
	settlement_status VARCHAR(20) NOT NULL,
	settlement_attempts INTEGER NOT NULL,
	settlement_error TEXT,
	settled_at TIMESTAMP WITH TIME ZONE,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_game_record_room_round UNIQUE (room_id, round_number),
	FOREIGN KEY(room_id) REFERENCES game_rooms (id) ON DELETE CASCADE
);

CREATE TABLE game_sessions (
	id SERIAL NOT NULL,
	room_id INTEGER NOT NULL,
	game_type VARCHAR(50) NOT NULL,
	current_turn VARCHAR(100),
	state JSONB NOT NULL,
	version INTEGER NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(room_id) REFERENCES game_rooms (id) ON DELETE CASCADE
);

CREATE TABLE game_states (
	id SERIAL NOT NULL,
	room_id INTEGER NOT NULL,
	game_type VARCHAR(50) NOT NULL,
	state JSONB NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(room_id) REFERENCES game_rooms (id) ON DELETE CASCADE
);

CREATE TABLE notifications (
	id SERIAL NOT NULL,
	user_id INTEGER NOT NULL,
	type VARCHAR(50) NOT NULL,
	title VARCHAR(100) NOT NULL,
	content TEXT NOT NULL,
	related_id INTEGER,
	is_read BOOLEAN NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE order_items (
	id SERIAL NOT NULL,
	order_id INTEGER NOT NULL,
	dish_id INTEGER NOT NULL,
	dish_name VARCHAR(100) NOT NULL,
	price FLOAT NOT NULL,
	quantity INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(order_id) REFERENCES orders (id),
	FOREIGN KEY(dish_id) REFERENCES dishes (id)
);

CREATE TABLE order_status_events (
	id SERIAL NOT NULL,
	order_id INTEGER NOT NULL,
	from_status VARCHAR(20),
	to_status VARCHAR(20) NOT NULL,
	actor_type VARCHAR(20) NOT NULL,
	actor_id VARCHAR(100) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(order_id) REFERENCES orders (id) ON DELETE CASCADE
);

CREATE TABLE reviews (
	id SERIAL NOT NULL,
	order_id INTEGER NOT NULL,
	rating INTEGER NOT NULL,
	want_again VARCHAR(20) NOT NULL,
	comment TEXT,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(order_id) REFERENCES orders (id)
);

CREATE TABLE user_achievements (
	id SERIAL NOT NULL,
	customer_id VARCHAR(100) NOT NULL,
	achievement_id INTEGER NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_user_achievement_customer_definition UNIQUE (customer_id, achievement_id),
	FOREIGN KEY(achievement_id) REFERENCES achievements (id)
);

CREATE TABLE wx_users (
	id SERIAL NOT NULL,
	customer_id VARCHAR(100) NOT NULL,
	app_id VARCHAR(64) NOT NULL,
	openid VARCHAR(128) NOT NULL,
	unionid VARCHAR(128),
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	last_login_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_wx_user_app_openid UNIQUE (app_id, openid),
	FOREIGN KEY(customer_id) REFERENCES customers (id) ON DELETE CASCADE
);

CREATE TABLE chess_moves (
	id SERIAL NOT NULL,
	game_id INTEGER NOT NULL,
	move_number INTEGER NOT NULL,
	player VARCHAR(100) NOT NULL,
	piece VARCHAR(40) NOT NULL,
	from_pos VARCHAR(8) NOT NULL,
	to_pos VARCHAR(8) NOT NULL,
	notation VARCHAR(80) NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_chess_move_game_number UNIQUE (game_id, move_number),
	FOREIGN KEY(game_id) REFERENCES chess_games (id) ON DELETE CASCADE
);

CREATE TABLE game_replays (
	id SERIAL NOT NULL,
	game_record_id INTEGER NOT NULL,
	game_type VARCHAR(50) NOT NULL,
	moves JSONB NOT NULL,
	final_state JSONB NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(game_record_id) REFERENCES game_records (id) ON DELETE CASCADE
);

CREATE TABLE love_tasks (
	id SERIAL NOT NULL,
	game_record_id INTEGER NOT NULL,
	player_id VARCHAR(100) NOT NULL,
	title VARCHAR(180) NOT NULL,
	status VARCHAR(20) NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	completed_at TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (id),
	CONSTRAINT uq_love_task_record_player UNIQUE (game_record_id, player_id),
	FOREIGN KEY(game_record_id) REFERENCES game_records (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX ix_achievements_code ON achievements (code);
CREATE INDEX ix_achievements_enabled ON achievements (enabled);
CREATE INDEX ix_achievements_game_type ON achievements (game_type);
CREATE INDEX ix_achievements_id ON achievements (id);
CREATE INDEX ix_admin_accounts_created_at ON admin_accounts (created_at);
CREATE INDEX ix_admin_accounts_id ON admin_accounts (id);
CREATE INDEX ix_admin_accounts_is_active ON admin_accounts (is_active);
CREATE INDEX ix_admin_accounts_last_login_at ON admin_accounts (last_login_at);
CREATE INDEX ix_admin_accounts_role ON admin_accounts (role);
CREATE UNIQUE INDEX ix_admin_accounts_username ON admin_accounts (username);
CREATE INDEX ix_ai_players_enabled ON ai_players (enabled);
CREATE INDEX ix_ai_players_game_type ON ai_players (game_type);
CREATE INDEX ix_ai_players_id ON ai_players (id);
CREATE INDEX ix_ai_players_level ON ai_players (level);
CREATE INDEX ix_customers_created_at ON customers (created_at);
CREATE INDEX ix_customers_is_active ON customers (is_active);
CREATE INDEX ix_customers_last_seen_at ON customers (last_seen_at);
CREATE UNIQUE INDEX ix_customers_legacy_customer_id ON customers (legacy_customer_id);
CREATE UNIQUE INDEX ix_customers_token_hash ON customers (token_hash);
CREATE INDEX ix_daily_tasks_completed_at ON daily_tasks (completed_at);
CREATE INDEX ix_daily_tasks_customer_id ON daily_tasks (customer_id);
CREATE INDEX ix_daily_tasks_date ON daily_tasks (date);
CREATE INDEX ix_daily_tasks_id ON daily_tasks (id);
CREATE INDEX ix_daily_tasks_status ON daily_tasks (status);
CREATE INDEX ix_daily_tasks_type ON daily_tasks (type);
CREATE INDEX ix_dishes_category ON dishes (category);
CREATE INDEX ix_dishes_id ON dishes (id);
CREATE INDEX ix_dishes_is_active ON dishes (is_active);
CREATE INDEX ix_game_events_enabled ON game_events (enabled);
CREATE INDEX ix_game_events_id ON game_events (id);
CREATE INDEX ix_game_events_type ON game_events (type);
CREATE INDEX ix_game_memories_created_at ON game_memories (created_at);
CREATE INDEX ix_game_memories_customer_id ON game_memories (customer_id);
CREATE INDEX ix_game_memories_event ON game_memories (event);
CREATE INDEX ix_game_memories_game_type ON game_memories (game_type);
CREATE INDEX ix_game_memories_id ON game_memories (id);
CREATE INDEX ix_game_memories_related_id ON game_memories (related_id);
CREATE INDEX ix_game_rooms_abandoned_at ON game_rooms (abandoned_at);
CREATE INDEX ix_game_rooms_created_at ON game_rooms (created_at);
CREATE INDEX ix_game_rooms_creator ON game_rooms (creator);
CREATE INDEX ix_game_rooms_expires_at ON game_rooms (expires_at);
CREATE INDEX ix_game_rooms_finished_at ON game_rooms (finished_at);
CREATE INDEX ix_game_rooms_game_type ON game_rooms (game_type);
CREATE INDEX ix_game_rooms_id ON game_rooms (id);
CREATE INDEX ix_game_rooms_last_activity_at ON game_rooms (last_activity_at);
CREATE INDEX ix_game_rooms_lease_expires_at ON game_rooms (lease_expires_at);
CREATE INDEX ix_game_rooms_owner_instance_id ON game_rooms (owner_instance_id);
CREATE UNIQUE INDEX ix_game_rooms_room_code ON game_rooms (room_code);
CREATE INDEX ix_game_rooms_status ON game_rooms (status);
CREATE INDEX ix_game_statistics_game_type ON game_statistics (game_type);
CREATE INDEX ix_game_statistics_id ON game_statistics (id);
CREATE INDEX ix_game_statistics_player_id ON game_statistics (player_id);
CREATE INDEX ix_game_statistics_updated_at ON game_statistics (updated_at);
CREATE INDEX ix_games_id ON games (id);
CREATE INDEX ix_games_status ON games (status);
CREATE UNIQUE INDEX ix_games_type ON games (type);
CREATE INDEX ix_love_scores_created_at ON love_scores (created_at);
CREATE INDEX ix_love_scores_customer_id ON love_scores (customer_id);
CREATE INDEX ix_love_scores_id ON love_scores (id);
CREATE INDEX ix_love_scores_related_id ON love_scores (related_id);
CREATE INDEX ix_love_scores_type ON love_scores (type);
CREATE INDEX ix_orders_created_at ON orders (created_at);
CREATE INDEX ix_orders_customer_id ON orders (customer_id);
CREATE INDEX ix_orders_desired_at ON orders (desired_at);
CREATE INDEX ix_orders_id ON orders (id);
CREATE UNIQUE INDEX ix_orders_idempotency_key ON orders (idempotency_key);
CREATE INDEX ix_orders_source_order_id ON orders (source_order_id);
CREATE INDEX ix_orders_status ON orders (status);
CREATE INDEX ix_orders_status_updated_at ON orders (status_updated_at);
CREATE INDEX ix_uploaded_images_created_at ON uploaded_images (created_at);
CREATE INDEX ix_users_created_at ON users (created_at);
CREATE INDEX ix_users_id ON users (id);
CREATE INDEX ix_users_role ON users (role);
CREATE UNIQUE INDEX ix_users_user_code ON users (user_code);
CREATE INDEX ix_admin_auth_events_admin_id ON admin_auth_events (admin_id);
CREATE INDEX ix_admin_auth_events_created_at ON admin_auth_events (created_at);
CREATE INDEX ix_admin_auth_events_id ON admin_auth_events (id);
CREATE INDEX ix_admin_auth_events_outcome ON admin_auth_events (outcome);
CREATE INDEX ix_admin_auth_events_username ON admin_auth_events (username);
CREATE INDEX ix_chess_games_black_player ON chess_games (black_player);
CREATE INDEX ix_chess_games_created_at ON chess_games (created_at);
CREATE INDEX ix_chess_games_finished_at ON chess_games (finished_at);
CREATE INDEX ix_chess_games_id ON chess_games (id);
CREATE INDEX ix_chess_games_red_player ON chess_games (red_player);
CREATE INDEX ix_chess_games_room_id ON chess_games (room_id);
CREATE INDEX ix_chess_games_winner ON chess_games (winner);
CREATE INDEX ix_couple_dates_created_at ON couple_dates (created_at);
CREATE INDEX ix_couple_dates_date ON couple_dates (date);
CREATE INDEX ix_couple_dates_id ON couple_dates (id);
CREATE INDEX ix_couple_dates_user_id ON couple_dates (user_id);
CREATE INDEX ix_couple_memories_created_at ON couple_memories (created_at);
CREATE INDEX ix_couple_memories_event_date ON couple_memories (event_date);
CREATE INDEX ix_couple_memories_id ON couple_memories (id);
CREATE INDEX ix_couple_memories_source_id ON couple_memories (source_id);
CREATE INDEX ix_couple_memories_source_type ON couple_memories (source_type);
CREATE INDEX ix_couple_memories_type ON couple_memories (type);
CREATE INDEX ix_couple_memories_user_id ON couple_memories (user_id);
CREATE INDEX ix_customer_sessions_created_at ON customer_sessions (created_at);
CREATE INDEX ix_customer_sessions_customer_id ON customer_sessions (customer_id);
CREATE INDEX ix_customer_sessions_expires_at ON customer_sessions (expires_at);
CREATE INDEX ix_customer_sessions_id ON customer_sessions (id);
CREATE INDEX ix_customer_sessions_last_seen_at ON customer_sessions (last_seen_at);
CREATE INDEX ix_customer_sessions_revoked_at ON customer_sessions (revoked_at);
CREATE INDEX ix_customer_sessions_rotated_from_id ON customer_sessions (rotated_from_id);
CREATE UNIQUE INDEX ix_customer_sessions_token_hash ON customer_sessions (token_hash);
CREATE INDEX ix_favorite_dishes_customer_id ON favorite_dishes (customer_id);
CREATE INDEX ix_favorite_dishes_dish_id ON favorite_dishes (dish_id);
CREATE INDEX ix_favorite_dishes_id ON favorite_dishes (id);
CREATE INDEX ix_game_actions_action_type ON game_actions (action_type);
CREATE INDEX ix_game_actions_client_action_id ON game_actions (client_action_id);
CREATE INDEX ix_game_actions_created_at ON game_actions (created_at);
CREATE INDEX ix_game_actions_id ON game_actions (id);
CREATE INDEX ix_game_actions_player_id ON game_actions (player_id);
CREATE INDEX ix_game_actions_room_id ON game_actions (room_id);
CREATE INDEX ix_game_event_logs_completed_at ON game_event_logs (completed_at);
CREATE INDEX ix_game_event_logs_created_at ON game_event_logs (created_at);
CREATE INDEX ix_game_event_logs_event_id ON game_event_logs (event_id);
CREATE INDEX ix_game_event_logs_id ON game_event_logs (id);
CREATE INDEX ix_game_event_logs_player_id ON game_event_logs (player_id);
CREATE INDEX ix_game_event_logs_room_id ON game_event_logs (room_id);
CREATE INDEX ix_game_event_logs_status ON game_event_logs (status);
CREATE INDEX ix_game_players_disconnected_at ON game_players (disconnected_at);
CREATE INDEX ix_game_players_expires_at ON game_players (expires_at);
CREATE INDEX ix_game_players_id ON game_players (id);
CREATE INDEX ix_game_players_joined_at ON game_players (joined_at);
CREATE INDEX ix_game_players_last_activity_at ON game_players (last_activity_at);
CREATE INDEX ix_game_players_player_id ON game_players (player_id);
CREATE INDEX ix_game_players_room_id ON game_players (room_id);
CREATE UNIQUE INDEX ix_game_players_room_session_token_hash ON game_players (room_session_token_hash);
CREATE INDEX ix_game_reconnect_tokens_created_at ON game_reconnect_tokens (created_at);
CREATE INDEX ix_game_reconnect_tokens_expires_at ON game_reconnect_tokens (expires_at);
CREATE INDEX ix_game_reconnect_tokens_id ON game_reconnect_tokens (id);
CREATE INDEX ix_game_reconnect_tokens_revoked ON game_reconnect_tokens (revoked);
CREATE INDEX ix_game_reconnect_tokens_room_id ON game_reconnect_tokens (room_id);
CREATE UNIQUE INDEX ix_game_reconnect_tokens_token_hash ON game_reconnect_tokens (token_hash);
CREATE INDEX ix_game_reconnect_tokens_user_id ON game_reconnect_tokens (user_id);
CREATE INDEX ix_game_records_created_at ON game_records (created_at);
CREATE INDEX ix_game_records_game_type ON game_records (game_type);
CREATE INDEX ix_game_records_id ON game_records (id);
CREATE INDEX ix_game_records_room_id ON game_records (room_id);
CREATE INDEX ix_game_records_settled_at ON game_records (settled_at);
CREATE INDEX ix_game_records_settlement_status ON game_records (settlement_status);
CREATE INDEX ix_game_records_winner ON game_records (winner);
CREATE INDEX ix_game_sessions_current_turn ON game_sessions (current_turn);
CREATE INDEX ix_game_sessions_game_type ON game_sessions (game_type);
CREATE INDEX ix_game_sessions_id ON game_sessions (id);
CREATE UNIQUE INDEX ix_game_sessions_room_id ON game_sessions (room_id);
CREATE INDEX ix_game_sessions_updated_at ON game_sessions (updated_at);
CREATE INDEX ix_game_states_game_type ON game_states (game_type);
CREATE INDEX ix_game_states_id ON game_states (id);
CREATE UNIQUE INDEX ix_game_states_room_id ON game_states (room_id);
CREATE INDEX ix_game_states_updated_at ON game_states (updated_at);
CREATE INDEX ix_notifications_created_at ON notifications (created_at);
CREATE INDEX ix_notifications_id ON notifications (id);
CREATE INDEX ix_notifications_is_read ON notifications (is_read);
CREATE INDEX ix_notifications_related_id ON notifications (related_id);
CREATE INDEX ix_notifications_type ON notifications (type);
CREATE INDEX ix_notifications_user_id ON notifications (user_id);
CREATE INDEX ix_order_items_id ON order_items (id);
CREATE INDEX ix_order_items_order_id ON order_items (order_id);
CREATE INDEX ix_order_status_events_created_at ON order_status_events (created_at);
CREATE INDEX ix_order_status_events_id ON order_status_events (id);
CREATE INDEX ix_order_status_events_order_id ON order_status_events (order_id);
CREATE INDEX ix_order_status_events_to_status ON order_status_events (to_status);
CREATE INDEX ix_reviews_id ON reviews (id);
CREATE UNIQUE INDEX ix_reviews_order_id ON reviews (order_id);
CREATE INDEX ix_user_achievements_achievement_id ON user_achievements (achievement_id);
CREATE INDEX ix_user_achievements_created_at ON user_achievements (created_at);
CREATE INDEX ix_user_achievements_customer_id ON user_achievements (customer_id);
CREATE INDEX ix_user_achievements_id ON user_achievements (id);
CREATE INDEX ix_wx_users_app_id ON wx_users (app_id);
CREATE INDEX ix_wx_users_created_at ON wx_users (created_at);
CREATE UNIQUE INDEX ix_wx_users_customer_id ON wx_users (customer_id);
CREATE INDEX ix_wx_users_id ON wx_users (id);
CREATE INDEX ix_wx_users_last_login_at ON wx_users (last_login_at);
CREATE INDEX ix_wx_users_openid ON wx_users (openid);
CREATE INDEX ix_wx_users_unionid ON wx_users (unionid);
CREATE INDEX ix_chess_moves_created_at ON chess_moves (created_at);
CREATE INDEX ix_chess_moves_game_id ON chess_moves (game_id);
CREATE INDEX ix_chess_moves_id ON chess_moves (id);
CREATE INDEX ix_chess_moves_player ON chess_moves (player);
CREATE INDEX ix_game_replays_created_at ON game_replays (created_at);
CREATE UNIQUE INDEX ix_game_replays_game_record_id ON game_replays (game_record_id);
CREATE INDEX ix_game_replays_game_type ON game_replays (game_type);
CREATE INDEX ix_game_replays_id ON game_replays (id);
CREATE INDEX ix_love_tasks_completed_at ON love_tasks (completed_at);
CREATE INDEX ix_love_tasks_created_at ON love_tasks (created_at);
CREATE INDEX ix_love_tasks_game_record_id ON love_tasks (game_record_id);
CREATE INDEX ix_love_tasks_id ON love_tasks (id);
CREATE INDEX ix_love_tasks_player_id ON love_tasks (player_id);
CREATE INDEX ix_love_tasks_status ON love_tasks (status);
