// Starts the Firebase emulators once for the emulator tests. The image is the one the Python
// integration tests build (tests/integration/firebase_emulator), so Docker reuses it.
import { fileURLToPath } from 'node:url';
import { GenericContainer, Wait } from 'testcontainers';
import { allowAllRules, clearDatabase } from '../support/emulator';

export const EMULATOR_IMAGE = 'pnls-firebase-database-emulator:test';
const EMULATOR_CONTEXT = fileURLToPath(
  new URL('../../../tests/integration/firebase_emulator', import.meta.url),
);

/** Starts the emulators, optionally on a Docker network where other containers reach them as "firebase". */
export async function startFirebaseEmulator(network) {
  await GenericContainer.fromDockerfile(EMULATOR_CONTEXT).build(
    EMULATOR_IMAGE,
    {
      deleteOnExit: false,
    },
  );
  let definition = new GenericContainer(EMULATOR_IMAGE);
  if (network) {
    definition = definition.withNetwork(network).withNetworkAliases('firebase');
  }
  const container = await definition
    .withExposedPorts(9000, 9099)
    .withWaitStrategy(Wait.forLogMessage('All emulators ready'))
    .withStartupTimeout(180_000)
    .start();
  const host = container.getHost();
  return {
    container,
    databaseHost: `${host}:${container.getMappedPort(9000)}`,
    authHost: `${host}:${container.getMappedPort(9099)}`,
  };
}

export default async function setup({ provide }) {
  const emulator = await startFirebaseEmulator();
  await allowAllRules(emulator.databaseHost);
  await clearDatabase(emulator.databaseHost);
  provide('databaseEmulatorHost', emulator.databaseHost);
  provide('authEmulatorHost', emulator.authHost);

  return async () => {
    await emulator.container.stop();
  };
}
