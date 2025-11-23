# UniMRCP Log Analyzer Makefile

.PHONY: help build clean security-check

help:
	@echo "Available commands:"
	@echo "  make build        - Parse log file and generate HTML report"
	@echo "  make clean        - Remove generated files"
	@echo "  make security-check - Check for potential security issues"
	@echo "  make help         - Show this help message"

build:
	@echo "Building report..."
	@python3 build_report.py

clean:
	@echo "Cleaning generated files..."
	@rm -f summary.json
	@rm -f report.html
	@echo "Clean complete"

security-check:
	@echo "🔒 Security Check"
	@echo "=================="
	@if [ -f .gitignore ]; then \
		echo "✅ .gitignore file exists"; \
	else \
		echo "❌ .gitignore file missing"; \
	fi
	@echo ""
	@echo "Checking for sensitive files that should not be committed:"
	@for file in *blue* *prod* *live* *internal*; do \
		if [ -f "$$file" ]; then \
			echo "⚠️  WARNING: Found potentially sensitive file: $$file"; \
		fi; \
	done
	@echo ""
	@echo "Checking git status for untracked sensitive files:"
	@if command -v git >/dev/null 2>&1; then \
		git status --porcelain | grep -E "(blue|prod|live|internal)" || echo "✅ No sensitive files in git status"; \
	else \
		echo "ℹ️  Git not available - cannot check git status"; \
	fi
