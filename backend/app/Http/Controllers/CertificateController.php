<?php

namespace App\Http\Controllers;

use App\Models\Certificate;
use Illuminate\Http\Request;
use Illuminate\Support\Str;

class CertificateController extends Controller
{
    public function index(Request $request)
    {
        $query = Certificate::query()->latest();

        if ($search = $request->string('search')->trim()->value()) {
            $query->where(function ($builder) use ($search) {
                $builder->where('public_id', 'like', "%{$search}%")
                    ->orWhere('recipient_name', 'like', "%{$search}%")
                    ->orWhere('event_name', 'like', "%{$search}%");
            });
        }

        if ($status = $request->string('status')->trim()->value()) {
            $query->where('status', $status);
        }

        return response()->json($query->paginate(25));
    }

    public function show(string $publicId)
    {
        return response()->json(Certificate::where('public_id', $publicId)->firstOrFail());
    }

    public function store(Request $request)
    {
        $data = $request->validate([
            'recipient_name' => ['required', 'string', 'max:255'],
            'recipient_email' => ['nullable', 'email', 'max:255'],
            'event_name' => ['required', 'string', 'max:255'],
            'certificate_type' => ['required', 'string', 'max:120'],
            'certificate_template_id' => ['nullable', 'integer', 'exists:certificate_templates,id'],
            'membership_type' => ['nullable', 'string', 'max:120'],
            'membership_number' => ['nullable', 'string', 'max:120'],
            'designation' => ['nullable', 'string', 'max:120'],
            'membership_starts_at' => ['nullable', 'date'],
            'valid_until' => ['nullable', 'date', 'after_or_equal:membership_starts_at'],
            'issued_on' => ['required', 'date'],
            'custom_fields' => ['nullable', 'array'],
            'custom_fields.*.label' => ['required_with:custom_fields', 'string', 'max:100'],
            'custom_fields.*.value' => ['nullable', 'string', 'max:500'],
            'template_layout' => ['nullable', 'array'],
        ]);

        $certificate = Certificate::create([
            ...$data,
            'uuid' => (string) Str::uuid(),
            'public_id' => $this->newPublicId($data['certificate_type']),
            'status' => 'VALID',
            'issued_by' => $request->user()?->id,
        ]);

        $certificate->audits()->create([
            'user_id' => $request->user()?->id,
            'action' => 'certificate.issued',
            'metadata' => ['public_id' => $certificate->public_id],
        ]);

        return response()->json($certificate, 201);
    }

    public function revoke(Request $request, string $publicId)
    {
        $certificate = Certificate::where('public_id', $publicId)->firstOrFail();
        abort_if($certificate->status === 'REVOKED', 422, 'Certificate is already revoked.');

        $certificate->update(['status' => 'REVOKED']);
        $certificate->audits()->create([
            'user_id' => $request->user()?->id,
            'action' => 'certificate.revoked',
            'metadata' => ['reason' => $request->string('reason')->trim()->value()],
        ]);

        return response()->json($certificate->fresh());
    }

    private function newPublicId(string $type): string
    {
        $prefix = match ($type) {
            'Certificate of Appreciation' => 'APP',
            'Certificate of Participation' => 'PAR',
            default => 'ACH',
        };

        do {
            $id = sprintf('UBV-%s-%s-%s', now()->format('Y'), $prefix, strtoupper(Str::random(8)));
        } while (Certificate::where('public_id', $id)->exists());

        return $id;
    }
}
