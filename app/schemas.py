from app import ma
from app.models import Time, Jogador, Arbitro, Estadio, Partida, EstatisticaPartida, Evento
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from marshmallow import fields, post_dump

class TimeSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Time
        load_instance = True
    
    @post_dump
    def normalize_fields(self, data, **kwargs):
        # Traduzir campos para inglês
        return {
            'id': data.get('id'),
            'name': data.get('nome'),
            'shield_url': data.get('escudo_url'),
            'created_at': data.get('created_at')
        }

class JogadorSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Jogador
        load_instance = True
    time_atual = fields.Nested(TimeSchema, only=("id", "name"))
    
    @post_dump
    def normalize_fields(self, data, **kwargs):
        normalized = {
            'id': data.get('id'),
            'name': data.get('nome'),
            'position': data.get('posicao'),
            'nationality': data.get('nacionalidade'),
            'birth_date': data.get('data_nascimento'),
            'source_id': data.get('id_fonte'),
            'metadata': data.get('meta_data')
        }
        if 'time_atual' in data:
            normalized['current_team'] = data['time_atual']
        return normalized

class ArbitroSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Arbitro
        load_instance = True
    
    @post_dump
    def normalize_fields(self, data, **kwargs):
        return {
            'id': data.get('id'),
            'name': data.get('nome'),
            'state': data.get('estado'),
            'category': data.get('categoria')
        }

class EstadioSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Estadio
        load_instance = True
    
    @post_dump
    def normalize_fields(self, data, **kwargs):
        return {
            'id': data.get('id'),
            'name': data.get('nome'),
            'city': data.get('cidade'),
            'state': data.get('estado'),
            'capacity': data.get('capacidade')
        }

class EstatisticaPartidaSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = EstatisticaPartida
        load_instance = True
    
    @post_dump
    def normalize_fields(self, data, **kwargs):
        return {
            'match_id': data.get('partida_id'),
            'possession_home': data.get('posse_casa'),
            'possession_away': data.get('posse_fora'),
            'shots_home': data.get('chutes_casa'),
            'shots_away': data.get('chutes_fora'),
            'xg_home': data.get('xg_casa'),
            'xg_away': data.get('xg_fora'),
            'metadata': data.get('meta_data'),
            'updated_at': data.get('updated_at')
        }

class EventoSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Evento
        load_instance = True
    time = fields.Nested(TimeSchema, only=("id", "name"))
    jogador = fields.Nested(JogadorSchema, only=("id", "name"))
    
    @post_dump
    def normalize_fields(self, data, **kwargs):
        normalized = {
            'id': data.get('id'),
            'match_id': data.get('partida_id'),
            'type': data.get('tipo'),
            'minute': data.get('minuto'),
            'period': data.get('periodo'),
            'description': data.get('descricao')
        }
        if 'time' in data:
            normalized['team'] = data['time']
        if 'jogador' in data:
            normalized['player'] = data['jogador']
        return normalized

class PartidaSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Partida
        load_instance = True
        include_fk = True

    time_casa = fields.Nested(TimeSchema, only=("id", "name"))
    time_fora = fields.Nested(TimeSchema, only=("id", "name"))
    estadio = fields.Nested(EstadioSchema, only=("id", "name"))
    arbitro = fields.Nested(ArbitroSchema, only=("id", "name"))
    estatisticas = fields.Nested(EstatisticaPartidaSchema)
    eventos = fields.List(fields.Nested(EventoSchema))
    
    @post_dump
    def normalize_fields(self, data, **kwargs):
        normalized = {
            'id': data.get('id'),
            'round': data.get('rodada'),
            'goals_home': data.get('gols_casa'),
            'goals_away': data.get('gols_fora'),
            'datetime': data.get('data_hora'),
            'attendance': data.get('publico'),
            'status': data.get('status'),
            'source_url': data.get('url_fonte'),
            'metadata': data.get('meta_data'),
            'created_at': data.get('created_at')
        }
        
        # Nested objects
        if 'time_casa' in data:
            normalized['home_team'] = data['time_casa']
        if 'time_fora' in data:
            normalized['away_team'] = data['time_fora']
        if 'estadio' in data:
            normalized['stadium'] = data['estadio']
        if 'arbitro' in data:
            normalized['referee'] = data['arbitro']
        if 'estatisticas' in data:
            normalized['statistics'] = data['estatisticas']
        if 'eventos' in data:
            normalized['events'] = data['eventos']
            
        return normalized
