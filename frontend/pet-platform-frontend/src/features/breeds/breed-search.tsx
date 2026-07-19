"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { AppShell } from "@/components/app-shell";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  Skeleton,
} from "@/components/primitives";
import { listBreeds, searchBreeds } from "@/lib/api/client";

const speciesLabelFa: Record<string, string> = { cat: "گربه", dog: "سگ" };

export function BreedSearch({ petId }: { petId?: string }) {
  const [query, setQuery] = useState("");
  const [species, setSpecies] = useState<"dog" | "cat" | undefined>(undefined);

  const listQuery = useQuery({
    queryKey: ["knowledge", "breeds", species],
    queryFn: () => listBreeds(species),
    enabled: query.trim().length === 0,
  });
  const searchQuery = useQuery({
    queryKey: ["knowledge", "breeds", "search", query, species],
    queryFn: () => searchBreeds(query, species),
    enabled: query.trim().length > 0,
  });

  const active = query.trim().length > 0 ? searchQuery : listQuery;

  return (
    <AppShell>
      <div className="stack">
        <div>
          <div className="eyebrow">دانش نژاد</div>
          <h1 className="display">جستجوی نژاد</h1>
        </div>

        <Card className="stack">
          <div className="field">
            <label htmlFor="breed-query">جستجو</label>
            <input
              id="breed-query"
              className="input"
              onChange={(event) => setQuery(event.target.value)}
              value={query}
            />
          </div>
          <div className="cluster" role="radiogroup" aria-label="گونه">
            {(
              [
                [undefined, "همه"],
                ["dog", "سگ"],
                ["cat", "گربه"],
              ] as const
            ).map(([value, label]) => (
              <Button
                key={label}
                type="button"
                variant={species === value ? "selection" : "secondary"}
                aria-pressed={species === value}
                onClick={() => setSpecies(value)}
              >
                {label}
              </Button>
            ))}
          </div>
        </Card>

        {active.isLoading ? (
          <Card className="stack">
            <Skeleton />
          </Card>
        ) : null}

        {active.isError ? (
          <ErrorState
            title="فهرست نژادها در دسترس نیست"
            action={
              <Button variant="secondary" onClick={() => void active.refetch()}>
                تلاش دوباره
              </Button>
            }
          />
        ) : null}

        {active.data?.items.length === 0 ? (
          <EmptyState title="نژادی یافت نشد" />
        ) : null}

        {active.data?.items.length ? (
          <ul className="stack" aria-label="فهرست نژادها">
            {active.data.items.map((breed) => (
              <li key={breed.id}>
                <Link
                  className="card split"
                  href={
                    petId
                      ? `/breeds/${breed.id}?petId=${petId}`
                      : `/breeds/${breed.id}`
                  }
                >
                  <span>{breed.name_fa}</span>
                  <span className="caption">
                    {speciesLabelFa[breed.species] ?? breed.species}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </AppShell>
  );
}
