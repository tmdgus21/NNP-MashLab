package com.potatomeet.app.ui.face.components

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.snapping.rememberSnapFlingBehavior
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun LockWheelColumn(
    items: List<String>,
    selectedIndex: Int,
    widthDp: Int = 62,
    onSelect: (Int) -> Unit,
) {
    val validIndex = if (selectedIndex in items.indices) selectedIndex else 0
    val listState = rememberLazyListState(initialFirstVisibleItemIndex = validIndex)
    val snapFlingBehavior = rememberSnapFlingBehavior(lazyListState = listState)
    val coroutineScope = rememberCoroutineScope()

    LaunchedEffect(listState.isScrollInProgress) {
        if (!listState.isScrollInProgress) {
            val layoutInfo = listState.layoutInfo
            val visibleItems = layoutInfo.visibleItemsInfo
            if (visibleItems.isNotEmpty()) {
                val containerCenter = layoutInfo.viewportStartOffset + (layoutInfo.viewportEndOffset - layoutInfo.viewportStartOffset) / 2
                val closestItem =
                    visibleItems.minByOrNull { item ->
                        kotlin.math.abs((item.offset + item.size / 2) - containerCenter)
                    }
                closestItem?.let {
                    if (it.index in items.indices && it.index != validIndex) {
                        onSelect(it.index)
                    }
                }
            }
        }
    }

    Box(
        modifier =
            Modifier
                .width(widthDp.dp)
                .height(76.dp)
                .clip(RoundedCornerShape(10.dp))
                .background(Color.White)
                .border(1.dp, Color(0xFFFFE082), RoundedCornerShape(10.dp)),
        contentAlignment = Alignment.Center,
    ) {
        Box(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .height(26.dp)
                    .background(Color(0xFFFFECB3).copy(alpha = 0.4f), RoundedCornerShape(6.dp)),
        )

        LazyColumn(
            state = listState,
            flingBehavior = snapFlingBehavior,
            modifier = Modifier.fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally,
            contentPadding = PaddingValues(vertical = 25.dp),
        ) {
            items(items.size) { index ->
                val isSelected = index == validIndex
                Box(
                    modifier =
                        Modifier
                            .fillMaxWidth()
                            .height(26.dp)
                            .clickable {
                                onSelect(index)
                                coroutineScope.launch {
                                    listState.animateScrollToItem(index)
                                }
                            },
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        text = items[index],
                        fontSize = if (isSelected) 12.sp else 10.sp,
                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                        color = if (isSelected) Color(0xFFFF8F00) else Color(0xFFB0BEC5),
                    )
                }
            }
        }
    }
}
