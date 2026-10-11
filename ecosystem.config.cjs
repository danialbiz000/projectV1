// PM2 config — usato su VPS Hetzner bare-metal
// Avvio: pm2 start ecosystem.config.cjs
// Startup: pm2 startup && pm2 save
module.exports = {
  apps: [
    {
      name: 'portfolio-nexus',
      script: 'server.js',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      env_file: '.env',
      env: {
        NODE_ENV: 'production',
      },
      error_file: 'logs/err.log',
      out_file: 'logs/out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
    },
  ],
};
