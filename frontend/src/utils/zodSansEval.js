import { z } from "zod";

// zod sonde `new Function` pour accélérer ses validations : la CSP l'interdit, à juste titre.
z.config({ jitless: true });
