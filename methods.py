from typing import List, Tuple

import numpy as np
import torch
import torchvision.transforms as T


def stack_image_with_spatialgrid(images: torch.Tensor) -> torch.Tensor:
    us = torch.arange(0, images.shape[-2], 1, dtype=torch.float32, device=images.device)
    vs = torch.arange(0, images.shape[-1], 1, dtype=torch.float32, device=images.device)
    grid = torch.meshgrid(us, vs, indexing='ij')
    spatial_grid = torch.stack(grid)

    tiled_spatial_grid = spatial_grid.unsqueeze(dim=0).tile(images.shape[0], 1, 1, 1)

    return torch.cat([images, tiled_spatial_grid], dim=1)


def destack_image_with_spatialgrid(augmented_image: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
    image = augmented_image[:, :3, :, :]
    spatial_grid = augmented_image[:, 3:, :]

    return image, spatial_grid


def get_random_augmentation(image: torch.Tensor) -> torch.Tensor:
    if 0 == np.random.randint(low=0, high=1):
        return T.RandomAffine(degrees=60, translate=(0, 0.5))(image)
    else:
        return T.RandomPerspective(distortion_scale=0.5, p=1.0)(image)


def augment_images_and_map_correspondence(images: torch.Tensor,
                                          n_correspondence: int) -> torch.Tensor:

    augmented_image_a = stack_image_with_spatialgrid(images)
    augmented_image_b = get_random_augmentation(stack_image_with_spatialgrid(images))

    augmented_images_a, grids_a = destack_image_with_spatialgrid(augmented_image_a)
    augmented_images_b, grids_b = destack_image_with_spatialgrid(augmented_image_b)

    matches_a: List[torch.Tensor] = []
    matches_b: List[torch.Tensor] = []

    # Compute correspondence from the spatial grid
    for grid_a, grid_b in zip(grids_a, grids_b):

        valid_pixels_a = torch.where(grid_a.mean(dim=0) != 0.0)

        us = valid_pixels_a[0]
        vs = valid_pixels_a[1]

        # Reducing computation costs
        trimming_indices = torch.linspace(0, us.shape[0] - 1, steps=5 * n_correspondence)
        trimming_indices = trimming_indices.type(torch.int64)
        us = us[trimming_indices].type(torch.float32)
        vs = vs[trimming_indices].type(torch.float32)

        valid_pixels_a = torch.vstack([us, vs]).permute(1, 0)
        tiled_valid_pixels_a = valid_pixels_a.view(valid_pixels_a.shape[0], valid_pixels_a.shape[1], 1, 1)

        spatial_grid_distances = torch.linalg.norm(torch.round(grid_b) - tiled_valid_pixels_a, dim=1)

        match_indices_a, ubs, vbs = torch.where(spatial_grid_distances == 0.0)

        mutual_match_a = valid_pixels_a[match_indices_a]
        mutual_match_b = torch.vstack([ubs, vbs]).permute(1, 0)

        trimming_indices = torch.linspace(0, mutual_match_a.shape[0] - 1, steps=n_correspondence)
        trimming_indices = trimming_indices.type(torch.int64)

        matches_a.append(mutual_match_a[trimming_indices])
        matches_b.append(mutual_match_b[trimming_indices])

    return augmented_images_a, torch.stack(matches_a), augmented_images_b, torch.stack(matches_b)