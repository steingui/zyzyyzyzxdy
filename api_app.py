from app import create_app
import os

app = create_app()

if __name__ == '__main__':
    # Porta padrão para desenvolvimento
    port = int(os.getenv('PORT', 5000))
    # Em desenvolvimento, usamos debug=True
    app.run(host='0.0.0.0', port=port, debug=True)
