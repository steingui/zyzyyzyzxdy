from app import ma
from app.models import Time, Jogador, Arbitro, Estadio, Partida, EstatisticaPartida, Evento
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from marshmallow import fields

class TimeSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Time
        load_instance = True

class JogadorSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Jogador
        load_instance = True
    time_atual = fields.Nested(TimeSchema, only=("id", "nome"))

class ArbitroSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Arbitro
        load_instance = True

class EstadioSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Estadio
        load_instance = True

class EstatisticaPartidaSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = EstatisticaPartida
        load_instance = True

class EventoSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Evento
        load_instance = True
    time = fields.Nested(TimeSchema, only=("id", "nome"))
    jogador = fields.Nested(JogadorSchema, only=("id", "nome"))

class PartidaSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Partida
        load_instance = True
        include_fk = True

    time_casa = fields.Nested(TimeSchema, only=("id", "nome"))
    time_fora = fields.Nested(TimeSchema, only=("id", "nome"))
    estadio = fields.Nested(EstadioSchema, only=("id", "nome"))
    arbitro = fields.Nested(ArbitroSchema, only=("id", "nome"))
    estatisticas = fields.Nested(EstatisticaPartidaSchema)
    eventos = fields.List(fields.Nested(EventoSchema))
