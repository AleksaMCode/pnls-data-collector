// Starts everything the dashboard talks to, on one Docker network, then builds and serves the dashboard:
//   - Postgres 17.6 (Supabase's version) with the stats service's Supabase migrations and seed rows,
//   - Redis, the stats API's cache,
//   - the Firebase Realtime Database and Authentication emulators,
//   - the stats API's own Docker image, in production mode, so it checks Firebase ID tokens.
// The browser reaches them on their mapped ports. Their addresses are saved in e2e/.state.json.
import { generateKeyPairSync } from 'node:crypto';
import {
  cpSync,
  mkdtempSync,
  readdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { GenericContainer, Network, Wait } from 'testcontainers';
import { build, preview } from 'vite';
import { allowAllRules } from '../test/support/emulator.js';
import { startFirebaseEmulator } from '../test/setup/emulatorGlobal.js';
import { seedSql } from './support/seed.js';
import { PREVIEW_PORT, STATE_FILE, TEST_USER } from './support/state.js';

const DASHBOARD = fileURLToPath(new URL('..', import.meta.url));
const REPO = join(DASHBOARD, '..');
const MIGRATIONS = join(REPO, 'stats', 'supabase', 'migrations');
// Keep in sync with SUPABASE_POSTGRES_IMAGE and REDIS_IMAGE in tests/integration/containers.py.
const SUPABASE_POSTGRES_IMAGE = 'postgres:17.6';
const REDIS_IMAGE = 'redis:8.8.0';
const STATS_API_IMAGE = 'pnls-stats-api:e2e';
const PROJECT_ID = 'demo-pnls';

async function exec(container, command) {
  const result = await container.exec(command);
  if (result.exitCode !== 0) {
    throw new Error(`${command.join(' ')} failed:\n${result.output}`);
  }
  return result.output;
}

async function startSupabase(network) {
  const container = await new GenericContainer(SUPABASE_POSTGRES_IMAGE)
    .withNetwork(network)
    .withNetworkAliases('supabase')
    .withEnvironment({ POSTGRES_PASSWORD: 'postgres' })
    .withExposedPorts(5432)
    .withWaitStrategy(
      Wait.forLogMessage('database system is ready to accept connections', 2),
    )
    .start();

  // Supabase CLI migrations are plain `<timestamp>_<name>.sql` files, applied in name order.
  const migrations = readdirSync(MIGRATIONS)
    .filter((name) => name.endsWith('.sql'))
    .sort();
  await container.copyContentToContainer([
    ...migrations.map((name) => ({
      content: readFileSync(join(MIGRATIONS, name), 'utf8'),
      target: `/migrations/${name}`,
    })),
    { content: seedSql(), target: '/seed.sql' },
  ]);
  for (const file of [
    ...migrations.map((name) => `/migrations/${name}`),
    '/seed.sql',
  ]) {
    await exec(container, [
      'psql',
      '-U',
      'postgres',
      '-v',
      'ON_ERROR_STOP=1',
      '-q',
      '-f',
      file,
    ]);
  }
  return container;
}

function startRedis(network) {
  return new GenericContainer(REDIS_IMAGE)
    .withNetwork(network)
    .withNetworkAliases('redis')
    .withWaitStrategy(Wait.forLogMessage('Ready to accept connections'))
    .start();
}

/** A service account that firebase-admin accepts. With an emulator host set, its key never signs anything. */
function fakeServiceAccount() {
  const { privateKey } = generateKeyPairSync('rsa', {
    modulusLength: 2048,
    privateKeyEncoding: { type: 'pkcs8', format: 'pem' },
    publicKeyEncoding: { type: 'spki', format: 'pem' },
  });
  return JSON.stringify({
    type: 'service_account',
    project_id: PROJECT_ID,
    private_key_id: 'e2e',
    private_key: privateKey,
    client_email: `e2e@${PROJECT_ID}.iam.gserviceaccount.com`,
    client_id: '0',
    token_uri: 'https://oauth2.googleapis.com/token',
  });
}

async function buildStatsApiImage() {
  // The image's build context is the repository root. Only stats_api/ is copied into a temporary
  // context, without a local .env, so no developer secrets reach the image.
  const context = mkdtempSync(join(tmpdir(), 'pnls-stats-api-'));
  cpSync(join(REPO, 'stats_api'), join(context, 'stats_api'), {
    recursive: true,
    filter: (source) => !/[\\/](\.env|__pycache__)$/.test(source),
  });
  try {
    await GenericContainer.fromDockerfile(
      context,
      'stats_api/Dockerfile',
    ).build(STATS_API_IMAGE, { deleteOnExit: false });
  } finally {
    rmSync(context, { recursive: true, force: true });
  }
}

function startStatsApi(network) {
  return new GenericContainer(STATS_API_IMAGE)
    .withNetwork(network)
    .withEnvironment({
      SERVER_ENV: 'production',
      SERVER_PORT: '9098',
      ALLOWED_ORIGINS: `http://localhost:${PREVIEW_PORT}`,
      SUPABASE_CONNECTION:
        'postgresql://postgres:postgres@supabase:5432/postgres',
      REDIS_CONNECTION: 'redis://redis:6379/0',
      REDIS_TTL: '60',
      FIREBASE_CREDENTIALS_JSON: fakeServiceAccount(),
      FIREBASE_AUTH_EMULATOR_HOST: 'firebase:9099',
      LOGFIRE_SEND_TO_LOGFIRE: 'false',
      LOGFIRE_IGNORE_NO_CONFIG: '1',
    })
    .withExposedPorts(9098)
    .withWaitStrategy(Wait.forHttp('/health', 9098).forStatusCode(200))
    .withStartupTimeout(60_000)
    .start();
}

async function createTestUser(authHost) {
  const response = await fetch(
    `http://${authHost}/identitytoolkit.googleapis.com/v1/accounts:signUp?key=test-api-key`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...TEST_USER, returnSecureToken: true }),
    },
  );
  if (!response.ok) {
    throw new Error(`Creating the test user failed: ${await response.text()}`);
  }
}

async function buildAndServeDashboard(env) {
  // Vite gives variables already in process.env priority over any local .env file.
  Object.assign(process.env, env);
  const outDir = join(DASHBOARD, 'e2e', '.dist');
  await build({
    root: DASHBOARD,
    mode: 'e2e',
    logLevel: 'warn',
    build: { outDir, emptyOutDir: true },
  });
  return preview({
    root: DASHBOARD,
    mode: 'e2e',
    build: { outDir },
    preview: { port: PREVIEW_PORT, strictPort: true, host: 'localhost' },
  });
}

export default async function globalSetup() {
  const network = await new Network().start();
  const [supabase, redis, firebase] = await Promise.all([
    startSupabase(network),
    startRedis(network),
    startFirebaseEmulator(network),
    buildStatsApiImage(),
  ]);
  const statsApi = await startStatsApi(network);
  await allowAllRules(firebase.databaseHost);
  await createTestUser(firebase.authHost);

  const statsApiUrl = `http://${statsApi.getHost()}:${statsApi.getMappedPort(9098)}`;
  const server = await buildAndServeDashboard({
    VITE_STATS_API_URL: statsApiUrl,
    VITE_FIREBASE_API_KEY: 'test-api-key',
    VITE_FIREBASE_AUTH_DOMAIN: `${PROJECT_ID}.firebaseapp.com`,
    VITE_FIREBASE_DATABASE_URL: `https://${PROJECT_ID}-default-rtdb.firebaseio.com`,
    VITE_FIREBASE_PROJECT_ID: PROJECT_ID,
    VITE_FIREBASE_STORAGE_BUCKET: '',
    VITE_FIREBASE_MESSAGING_SENDER_ID: '',
    VITE_FIREBASE_APP_ID: '',
    VITE_FIREBASE_AUTH_EMULATOR_HOST: firebase.authHost,
    VITE_FIREBASE_DATABASE_EMULATOR_HOST: firebase.databaseHost,
  });

  writeFileSync(
    STATE_FILE,
    JSON.stringify({
      statsApiUrl,
      databaseEmulatorHost: firebase.databaseHost,
      authEmulatorHost: firebase.authHost,
    }),
  );

  return async () => {
    await new Promise((resolve) => server.httpServer.close(resolve));
    await Promise.all(
      [statsApi, supabase, redis, firebase.container].map((c) => c.stop()),
    );
    await network.stop();
    rmSync(STATE_FILE, { force: true });
  };
}
