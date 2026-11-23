.PHONY: clean-install install fmt run build preview audit audit-fix

clean-install:
	rm -rf node_modules package-lock.json
	npm install

install:
	npm install

fmt:
	npx prettier --write .

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
