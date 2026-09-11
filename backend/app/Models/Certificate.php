<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\MorphMany;

class Certificate extends Model
{
    protected $fillable = [
        'uuid', 'public_id', 'certificate_template_id', 'issued_by', 'recipient_name',
        'recipient_email', 'event_name', 'certificate_type', 'membership_type',
        'membership_number', 'designation', 'membership_starts_at', 'valid_until',
        'issued_on', 'status', 'custom_fields', 'template_layout', 'pdf_path',
    ];

    protected function casts(): array
    {
        return [
            'membership_starts_at' => 'date', 'valid_until' => 'date', 'issued_on' => 'date',
            'custom_fields' => 'array', 'template_layout' => 'array',
        ];
    }

    public function template(): BelongsTo
    {
        return $this->belongsTo(CertificateTemplate::class, 'certificate_template_id');
    }

    public function audits(): MorphMany
    {
        return $this->morphMany(AuditLog::class, 'auditable');
    }
}
