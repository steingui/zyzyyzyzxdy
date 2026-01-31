from app import db
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB

class Time(db.Model):
    __tablename__ = 'times'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    escudo_url = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Jogador(db.Model):
    __tablename__ = 'jogadores'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    time_atual_id = db.Column(db.Integer, db.ForeignKey('times.id'))
    posicao = db.Column(db.String(50))
    nacionalidade = db.Column(db.String(50))
    data_nascimento = db.Column(db.Date)
    id_fonte = db.Column(db.String(100))
    meta_data = db.Column("metadata", JSONB, default={})
    
    time_atual = db.relationship('Time', backref='jogadores')

class Arbitro(db.Model):
    __tablename__ = 'arbitros'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), unique=True, nullable=False)
    estado = db.Column(db.String(2))
    categoria = db.Column(db.String(50))

class Estadio(db.Model):
    __tablename__ = 'estadios'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), unique=True, nullable=False)
    cidade = db.Column(db.String(100))
    estado = db.Column(db.String(2))
    capacidade = db.Column(db.Integer)

class Partida(db.Model):
    __tablename__ = 'partidas'
    id = db.Column(db.Integer, primary_key=True)
    rodada = db.Column(db.Integer, nullable=False)
    time_casa_id = db.Column(db.Integer, db.ForeignKey('times.id'), nullable=False)
    time_fora_id = db.Column(db.Integer, db.ForeignKey('times.id'), nullable=False)
    gols_casa = db.Column(db.Integer, default=0)
    gols_fora = db.Column(db.Integer, default=0)
    data_hora = db.Column(db.DateTime)
    estadio_id = db.Column(db.Integer, db.ForeignKey('estadios.id'))
    arbitro_id = db.Column(db.Integer, db.ForeignKey('arbitros.id'))
    publico = db.Column(db.Integer)
    status = db.Column(db.String(20), default='scheduled')
    url_fonte = db.Column(db.String(255), unique=True)
    meta_data = db.Column("metadata", JSONB, default={})
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    time_casa = db.relationship('Time', foreign_keys=[time_casa_id], backref='jogos_casa')
    time_fora = db.relationship('Time', foreign_keys=[time_fora_id], backref='jogos_fora')
    estadio = db.relationship('Estadio', backref='partidas')
    arbitro = db.relationship('Arbitro', backref='partidas')

class EstatisticaPartida(db.Model):
    __tablename__ = 'estatisticas_partida'
    partida_id = db.Column(db.Integer, db.ForeignKey('partidas.id'), primary_key=True)
    posse_casa = db.Column(db.Integer)
    posse_fora = db.Column(db.Integer)
    chutes_casa = db.Column(db.Integer)
    chutes_fora = db.Column(db.Integer)
    xg_casa = db.Column(db.Float)
    xg_fora = db.Column(db.Float)
    # Outros campos omitidos por brevidade, mas o JSONB metadata captura tudo
    meta_data = db.Column("metadata", JSONB, default={})
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    partida = db.relationship('Partida', backref=db.backref('estatisticas', uselist=False))

class Evento(db.Model):
    __tablename__ = 'eventos'
    id = db.Column(db.Integer, primary_key=True)
    partida_id = db.Column(db.Integer, db.ForeignKey('partidas.id'), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    minuto = db.Column(db.Integer)
    periodo = db.Column(db.Integer)
    time_id = db.Column(db.Integer, db.ForeignKey('times.id'))
    jogador_id = db.Column(db.Integer, db.ForeignKey('jogadores.id'))
    descricao = db.Column(db.Text)

    partida = db.relationship('Partida', backref='eventos')
    time = db.relationship('Time', backref='eventos')
    jogador = db.relationship('Jogador', backref='eventos')
