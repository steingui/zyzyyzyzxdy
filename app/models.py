from app import db
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Index, JSON

# ====================
# NEW MODELS: MULTI-LEAGUE SUPPORT (STANDARDIZED PT-BR)
# ====================

class Liga(db.Model):
    __tablename__ = 'ligas'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False)
    pais = db.Column(db.String(100), nullable=False)
    confederacao = db.Column(db.String(20))
    num_times = db.Column(db.Integer, default=20)
    num_rodadas = db.Column(db.Integer, default=38)
    ogol_slug = db.Column(db.String(100))
    meta_data = db.Column("metadata", JSON().with_variant(JSONB, "postgresql"), default={})
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    temporadas = db.relationship('Temporada', back_populates='liga', cascade='all, delete-orphan')
    times = db.relationship('Time', back_populates='liga')

class Temporada(db.Model):
    __tablename__ = 'temporadas'
    id = db.Column(db.Integer, primary_key=True)
    liga_id = db.Column(db.Integer, db.ForeignKey('ligas.id'), nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    data_inicio = db.Column(db.Date)
    data_fim = db.Column(db.Date)
    is_current = db.Column(db.Boolean, default=False)
    ogol_edition_id = db.Column(db.String(50))
    meta_data = db.Column("metadata", JSON().with_variant(JSONB, "postgresql"), default={})
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    liga = db.relationship('Liga', back_populates='temporadas')
    partidas = db.relationship('Partida', back_populates='temporada')
    times_temporadas = db.relationship('TimeTemporada', back_populates='temporada', cascade='all, delete-orphan')

    # Indexes
    __table_args__ = (
        Index('idx_active_seasons', 'liga_id', postgresql_where=(is_current == True)),
    )

class TimeTemporada(db.Model):
    __tablename__ = 'times_temporadas'
    id = db.Column(db.Integer, primary_key=True)
    time_id = db.Column(db.Integer, db.ForeignKey('times.id'), nullable=False)
    temporada_id = db.Column(db.Integer, db.ForeignKey('temporadas.id'), nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    posicao = db.Column(db.Integer)
    pontos = db.Column(db.Integer)
    vitorias = db.Column(db.Integer, default=0)
    empates = db.Column(db.Integer, default=0)
    derrotas = db.Column(db.Integer, default=0)
    gols_pro = db.Column(db.Integer, default=0)
    gols_contra = db.Column(db.Integer, default=0)
    meta_data = db.Column("metadata", JSON().with_variant(JSONB, "postgresql"), default={})
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    time = db.relationship('Time', back_populates='times_temporadas')
    temporada = db.relationship('Temporada', back_populates='times_temporadas')

    # Indexes/Constraints
    __table_args__ = (
        db.UniqueConstraint('time_id', 'temporada_id', name='time_temporada_unica'),
        Index('idx_times_temporadas_posicao', 'temporada_id', 'posicao'),
        Index('idx_team_seasons_lookup', 'time_id', 'temporada_id'),
    )

# ====================
# CORE MODELS
# ====================

class Time(db.Model):
    __tablename__ = 'times'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    escudo_url = db.Column(db.Text)
    liga_id = db.Column(db.Integer, db.ForeignKey('ligas.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    liga = db.relationship('Liga', back_populates='times')
    times_temporadas = db.relationship('TimeTemporada', back_populates='time', cascade='all, delete-orphan')

class Jogador(db.Model):
    __tablename__ = 'jogadores'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    time_atual_id = db.Column(db.Integer, db.ForeignKey('times.id'))
    posicao = db.Column(db.String(50))
    nacionalidade = db.Column(db.String(50))
    data_nascimento = db.Column(db.Date)
    id_fonte = db.Column(db.String(100))
    meta_data = db.Column("metadata", JSON().with_variant(JSONB, "postgresql"), default={})
    
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
    temporada_id = db.Column(db.Integer, db.ForeignKey('temporadas.id'), nullable=False)
    rodada = db.Column(db.Integer, nullable=False)
    time_casa_id = db.Column(db.Integer, db.ForeignKey('times.id'), nullable=False)
    time_fora_id = db.Column(db.Integer, db.ForeignKey('times.id'), nullable=False)
    gols_casa = db.Column(db.Integer, default=0)
    gols_fora = db.Column(db.Integer, default=0)
    gols_casa_intervalo = db.Column(db.Integer)
    gols_fora_intervalo = db.Column(db.Integer)
    data_hora = db.Column(db.DateTime)
    estadio_id = db.Column(db.Integer, db.ForeignKey('estadios.id'))
    arbitro_id = db.Column(db.Integer, db.ForeignKey('arbitros.id'))
    publico = db.Column(db.Integer)
    status = db.Column(db.String(20), default='scheduled')
    url_fonte = db.Column(db.String(255), unique=True)
    meta_data = db.Column("metadata", JSON().with_variant(JSONB, "postgresql"), default={})
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    start_time = db.Column(db.DateTime)
    # Denormalized context for strict querying
    liga_id = db.Column(db.Integer, db.ForeignKey('ligas.id'))
    ano = db.Column(db.Integer)

    # Relationships
    temporada = db.relationship('Temporada', back_populates='partidas')
    liga = db.relationship('Liga', backref='partidas')
    time_casa = db.relationship('Time', foreign_keys=[time_casa_id], backref='jogos_casa')
    time_fora = db.relationship('Time', foreign_keys=[time_fora_id], backref='jogos_fora')
    estadio = db.relationship('Estadio', backref='partidas')
    arbitro = db.relationship('Arbitro', backref='partidas')

    # Indexes
    __table_args__ = (
        # Dashboard High-Performance Index (Covering Index)
        Index('idx_partidas_dashboard', 'temporada_id', 'status', 'data_hora', 
              postgresql_include=['id', 'time_casa_id', 'time_fora_id', 'gols_casa', 'gols_fora']),
        # Team History High-Performance Indexes
        Index('idx_partidas_time_casa_history', 'time_casa_id', 'data_hora'),
        Index('idx_partidas_time_fora_history', 'time_fora_id', 'data_hora'),
        # RFC Optimization Indexes
        Index('idx_partidas_season_round', 'temporada_id', 'rodada'),
        Index('idx_partidas_teams', 'time_casa_id', 'time_fora_id'),
        # Uniqueness
        db.UniqueConstraint('temporada_id', 'rodada', 'time_casa_id', 'time_fora_id', name='partida_unica'),
    )

class EstatisticaPartida(db.Model):
    __tablename__ = 'estatisticas_partidas'  # Pluralized
    partida_id = db.Column(db.Integer, db.ForeignKey('partidas.id'), primary_key=True)
    posse_casa = db.Column(db.Integer)
    posse_fora = db.Column(db.Integer)
    chutes_casa = db.Column(db.Integer)
    chutes_fora = db.Column(db.Integer)
    chutes_gol_casa = db.Column(db.Integer)
    chutes_gol_fora = db.Column(db.Integer)
    chutes_bloqueados_casa = db.Column(db.Integer)
    chutes_bloqueados_fora = db.Column(db.Integer)
    escanteios_casa = db.Column(db.Integer)
    escanteios_fora = db.Column(db.Integer)
    xg_casa = db.Column(db.Float)
    xg_fora = db.Column(db.Float)
    xgot_casa = db.Column(db.Float)
    xgot_fora = db.Column(db.Float)
    passes_casa = db.Column(db.Integer)
    passes_fora = db.Column(db.Integer)
    passes_certos_casa = db.Column(db.Integer)
    passes_certos_fora = db.Column(db.Integer)
    passes_precisao_casa = db.Column(db.Float)
    passes_precisao_fora = db.Column(db.Float)
    faltas_casa = db.Column(db.Integer)
    faltas_fora = db.Column(db.Integer)
    impedimentos_casa = db.Column(db.Integer)
    impedimentos_fora = db.Column(db.Integer)
    defesas_goleiro_casa = db.Column(db.Integer)
    defesas_goleiro_fora = db.Column(db.Integer)
    cortes_casa = db.Column(db.Integer)
    cortes_fora = db.Column(db.Integer)
    interceptacoes_casa = db.Column(db.Integer)
    interceptacoes_fora = db.Column(db.Integer)
    amarelos_casa = db.Column(db.Integer)
    amarelos_fora = db.Column(db.Integer)
    vermelhos_casa = db.Column(db.Integer)
    vermelhos_fora = db.Column(db.Integer)
    duelos_ganhos_casa = db.Column(db.Integer)
    duelos_ganhos_fora = db.Column(db.Integer)
    duelos_aereos_ganhos_casa = db.Column(db.Integer)
    duelos_aereos_ganhos_fora = db.Column(db.Integer)
    meta_data = db.Column("metadata", JSON().with_variant(JSONB, "postgresql"), default={})
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    partida = db.relationship('Partida', backref=db.backref('estatisticas', uselist=False))

    # Indexes
    __table_args__ = (
        Index('idx_estatisticas_xg', 'xg_casa', 'xg_fora'),
    )

class Evento(db.Model):
    __tablename__ = 'eventos'
    id = db.Column(db.Integer, primary_key=True)
    partida_id = db.Column(db.Integer, db.ForeignKey('partidas.id'), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    minuto = db.Column(db.Integer)
    minuto_adicional = db.Column(db.Integer, default=0)
    periodo = db.Column(db.Integer)
    time_id = db.Column(db.Integer, db.ForeignKey('times.id'))
    jogador_id = db.Column(db.Integer, db.ForeignKey('jogadores.id'))
    jogador_secundario_id = db.Column(db.Integer, db.ForeignKey('jogadores.id'))
    descricao = db.Column(db.Text)

    partida = db.relationship('Partida', backref='eventos')
    time = db.relationship('Time', backref='eventos')
    jogador = db.relationship('Jogador', foreign_keys=[jogador_id], backref='eventos')
    jogador_secundario = db.relationship('Jogador', foreign_keys=[jogador_secundario_id], backref='eventos_secundarios')
    
    # Indexes
    __table_args__ = (
        Index('idx_eventos_timeline', 'partida_id', 'periodo', 'minuto'),
    )

class Escalacao(db.Model):
    __tablename__ = 'escalacoes'
    partida_id = db.Column(db.Integer, db.ForeignKey('partidas.id'), primary_key=True)
    jogador_id = db.Column(db.Integer, db.ForeignKey('jogadores.id'), primary_key=True)
    time_id = db.Column(db.Integer, db.ForeignKey('times.id'), nullable=False)
    titular = db.Column(db.Boolean, default=False)
    numero_camisa = db.Column(db.String(10))
    nota = db.Column(db.Float)
    stats = db.Column(JSON().with_variant(JSONB, "postgresql"), default={})
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    partida = db.relationship('Partida', backref='escalacoes')
    jogador = db.relationship('Jogador', backref='escalacoes')
    time = db.relationship('Time', backref='escalacoes')
