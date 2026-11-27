.PHONY: clean-install install fmt lint run build preview audit audit-fix test test-unit test-integration test-emulator test-e2e coverage

clean-install:
	rm -rf node_modules package-lock.json
	npm install

install:
	npm install

fmt:
	npx prettier --write .

lint:
	npm run lint

run:
	npm run dev

build:
	npm run build

preview:
	npm run preview

audit:
	npm audit

audit-fix:
	npm audit fix

# `test` runs the unit and integration tests, which need nothing but Node.
# `test-emulator` and `test-e2e` start Docker containers (the Firebase emulators; for e2e also the
# stats API, Postgres and Redis). Install Chromium once for e2e with `npx playwright install chromium`.
test:
	npm test

test-unit:
	npm run test:unit

test-integration:
	npm run test:integration

test-emulator:
	npm run test:emulator

test-e2e:
	npm run test:e2e

coverage:
	npm run test:coverage
