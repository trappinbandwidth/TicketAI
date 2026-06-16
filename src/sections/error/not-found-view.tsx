import { RouterLink } from 'src/routes/components';
import { Button } from 'src/components/ui';

import { SimpleLayout } from 'src/layouts/simple';

// ----------------------------------------------------------------------

export function NotFoundView() {
  return (
    <SimpleLayout content={{ compact: true }}>
      <div className="mx-auto w-full max-w-xl px-4 text-center">
        <h1 className="mb-2 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
          Sorry, page not found!
        </h1>

        <p className="text-sm leading-6 text-slate-500 sm:text-base">
          Sorry, we couldn’t find the page you’re looking for. Perhaps you’ve mistyped the URL? Be
          sure to check your spelling.
        </p>

        <img
          src="/assets/notfount404.svg"
          alt="404 illustration"
          className="mx-auto my-10 h-auto w-80 max-w-full sm:my-14"
        />

        <Button asChild size="lg" className="mx-auto min-w-40">
          <RouterLink href="/">Go to home</RouterLink>
        </Button>
      </div>
    </SimpleLayout>
  );
}
