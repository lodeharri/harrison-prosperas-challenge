---
name: frontend-scaffold
description: Workflow for project initialization using Vite, Tailwind CSS, and SweetAlert2.
---

# Instructions for Frontend Scaffolding

1. **Initialization**: Use `npm create vite@latest . -- --template react-ts` to scaffold.
2. **Tailwind Integration**: 
   - Install `tailwindcss`, `postcss`, and `autoprefixer`.
   - Initialize `tailwind.config.js` with content paths for all components.
   - Inject `@tailwind` directives into the main CSS entrypoint.
3. **Responsive Baseline**: Configure a mobile-first viewport meta tag and standard Tailwind breakpoints.
4. **SweetAlert2 Config**: Install `sweetalert2` and create a centralized utility in `src/services/notifications.ts` for consistent UI feedback.

## Verification
- Confirm `vite.config.ts` is present.
- Verify Tailwind classes are building via a smoke test on `App.tsx`.