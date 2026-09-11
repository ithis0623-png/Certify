<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::create('certificates', function (Blueprint $table) {
            $table->id();
            $table->uuid('uuid')->unique();
            $table->string('public_id')->unique();
            $table->unsignedBigInteger('certificate_template_id')->nullable();
            $table->foreignId('issued_by')->nullable()->constrained('users')->nullOnDelete();
            $table->string('recipient_name');
            $table->string('recipient_email')->nullable()->index();
            $table->string('event_name')->index();
            $table->string('certificate_type');
            $table->string('membership_type')->nullable();
            $table->string('membership_number')->nullable()->index();
            $table->string('designation')->nullable();
            $table->date('membership_starts_at')->nullable();
            $table->date('valid_until')->nullable()->index();
            $table->date('issued_on');
            $table->string('status')->default('VALID')->index();
            $table->json('custom_fields')->nullable();
            $table->json('template_layout')->nullable();
            $table->string('pdf_path')->nullable();
            $table->timestamps();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('certificates');
    }
};
